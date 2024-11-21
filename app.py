from flask import Flask, request, jsonify, render_template
from static_data import price_list, item_name_mapping, size_required_items, menu_items
from flask_cors import CORS
import os
import json
import re

app = Flask(__name__)
CORS(app)

# Global storage for orders and pending orders
orders = {}
pending_orders = {}
last_ordered_item = {}
awaiting_order_confirmation = {}
awaiting_menu_response = {}  # Track menu query follow-ups
awaiting_more_items = {}  # Track if we're asking about additional items

# Add a function to clear orders for a session


def clear_session_data(session_id):
    if session_id in orders:
        del orders[session_id]
    if session_id in pending_orders:
        del pending_orders[session_id]
    if session_id in last_ordered_item:
        del last_ordered_item[session_id]
    if session_id in awaiting_order_confirmation:
        del awaiting_order_confirmation[session_id]
    if session_id in awaiting_menu_response:
        del awaiting_menu_response[session_id]
    if session_id in awaiting_more_items:
        del awaiting_more_items[session_id]


# Add these new global variables at the top
drink_name_mapping = {
    "Coke": "Soft Drink",
    "Coca-Cola": "Soft Drink",
    "Sprite": "Soft Drink",
    "Dr Pepper": "Soft Drink",
    "Diet Coke": "Soft Drink",
    "Pepsi": "Soft Drink"
}

item_modifications = {
    "add": {},
    "remove": {}
}

# Add this helper function for quantity parsing


def parse_quantity(text):
    number_words = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    return number_words.get(text.lower(), 1)


def calculate_total(order_items):
    total = 0
    for item in order_items:
        food_item = item['food_item']
        quantity = item.get('quantity', 1)
        # Get base price from price list
        price = price_list.get(food_item, 0)
        total += price * quantity
    return total


# Add this mapping for items that need prefixes
item_prefix_mapping = {
    "Cool Wrap": "Grilled Cool Wrap",
    # Add other items that need prefixes
}

# Add this helper function


def create_response(message):
    return jsonify({
        'fulfillmentText': message,
        'fulfillmentMessages': [
            {
                'text': {
                    'text': [message]
                }
            }
        ]
    })


# Add these helper functions near the top with other helpers
def get_menu_items_by_category(category):
    category_mapping = {
        'sandwiches': ['Chicken Sandwich', 'Deluxe Chicken Sandwich', 'Spicy Chicken Sandwich',
                       'Spicy Deluxe Sandwich', 'Grilled Chicken Sandwich', 'Grilled Chicken Club Sandwich'],
        'salads': ['Cobb Salad', 'Spicy Southwest Salad', 'Market Salad', 'Side Salad'],
        'drinks': [item for item in menu_items.keys() if any(x in item for x in ['Drink', 'Lemonade', 'Tea', 'Coffee', 'Milk', 'Sunjoy'])],
        'desserts': [item for item in menu_items.keys() if any(x in item for x in ['Milkshake', 'Cookie', 'Icedream', 'Brownie'])],
        'sides': [item for item in menu_items.keys() if any(x in item for x in ['Fries', 'Mac & Cheese', 'Fruit Cup', 'Soup'])]
    }
    return category_mapping.get(category.lower(), [])


def format_menu_item_details(item_name):
    item = menu_items.get(item_name)
    if not item:
        return None

    price = item['price']
    ingredients = ', '.join(item['ingredients'])
    return f"{item_name}: ${price:.2f}\nIngredients: {ingredients}"


def get_full_item_name(item_name):
    """Convert partial item names to their full menu item names"""
    # Check direct mapping first
    if item_name in item_name_mapping:
        base_name = item_name_mapping[item_name]
    else:
        base_name = item_name

    # If item requires size and no size specified, return small by default
    if base_name in size_required_items:
        if not any(size in item_name.lower() for size in ['small', 'medium', 'large']):
            return f"{base_name} (Small)"

    # Search for exact match first
    for menu_item in menu_items.keys():
        if base_name.lower() == menu_item.lower():
            return menu_item

    # If no exact match, search for partial match
    for menu_item in menu_items.keys():
        if base_name.lower() in menu_item.lower():
            return menu_item

    return None


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("\n=== WEBHOOK REQUEST ===")
        req = request.get_json(silent=True, force=True)

        # Detailed debug logging
        query_result = req.get('queryResult', {})
        intent = query_result.get('intent', {})

        print("Intent Data:", {
            'displayName': intent.get('displayName'),
            'parameters': query_result.get('parameters'),
            'queryText': query_result.get('queryText'),
            'fulfillmentText': query_result.get('fulfillmentText')
        })

        # Check if intent names match exactly
        intent_name = intent.get('displayName')
        print(f"Received intent: '{intent_name}'")
        print(f"Intent type: {type(intent_name)}")  # Check if it's a string

        if req is None:
            return jsonify({'fulfillmentText': "Invalid request format."})

        print("Raw Request:", json.dumps(req, indent=2))

        session_id = req.get('session')
        query_result = req.get('queryResult', {})
        intent_name = query_result.get('intent', {}).get('displayName')
        query_text = query_result.get('queryText', '').lower()
        parameters = query_result.get('parameters', {})

        # Initialize orders if needed
        if session_id not in orders:
            orders[session_id] = []

        print(f"Session ID: {session_id}")
        print(f"Received intent: {intent_name}")
        print(f"Query Text: {query_text}")
        print(f"Parameters: {parameters}")
        print(
            f"Current orders before processing: {orders.get(session_id, [])}")

        # Print out all your handled intents for comparison
        HANDLED_INTENTS = [
            'OrderFood',
            'OrderFood - size',
            'SpecifySize',
            'ModifyOrder',
            'SandwichSpicyOrNot',
            'SandwichSpicyOrNot - custom',
            'SandwichSpicyOrNot - custom-2',
            'ReviewOrder',
            'OrderCompletion',
            'ConfirmOrder',
            'Default Welcome Intent',
            'MenuQuery',
            'Yes',
            'No'
        ]
        print(
            f"Is intent '{intent_name}' in handled intents? {intent_name in HANDLED_INTENTS}")

        if intent_name == 'OrderFood':
            # Check if this is a price inquiry
            if 'how much' in query_text.lower() or 'cost' in query_text.lower() or 'price' in query_text.lower():
                # Extract the item they're asking about
                food_items = parameters.get('FoodItem', [])
                if food_items:
                    item_name = food_items[0]  # Get the first item
                    price = price_list.get(item_name)
                    if price:
                        # Set menu context for follow-up
                        if session_id not in awaiting_menu_response:
                            awaiting_menu_response[session_id] = {}
                        awaiting_menu_response[session_id] = {
                            'item': item_name,
                            'asked_about': 'order'
                        }
                        return create_response(f"A {item_name} costs ${price:.2f}. Would you like to order one?")
                    else:
                        return create_response("I couldn't find the price for that item. Could you please specify the exact menu item?")
            
            # Continue with regular order processing
            food_items = parameters.get('FoodItem', [])
            sizes = parameters.get('Size', '')
            numbers = parameters.get('number', [])
            query = query_text.lower()

            # Initialize order items if not exists
            if session_id not in orders:
                orders[session_id] = []

            # Extract all quantities and items using regex
            matches = re.findall(r'(\d+)\s+((?:small|medium|large|)\s*[a-zA-Z\s]+)(?:,|\s+and\s+|\s*$)', query)
            
            for quantity, item in matches:
                quantity = int(quantity)
                item = item.strip()
                
                # Handle drinks
                if 'drink' in item:
                    size = 'Small'
                    if 'large' in item:
                        size = 'Large'
                    elif 'medium' in item:
                        size = 'Medium'
                    orders[session_id].append({
                        'food_item': f"Soft Drink ({size})",
                        'quantity': quantity
                    })
                    
                # Handle fries
                elif 'fries' in item:
                    size = 'Small'
                    if 'large' in item:
                        size = 'Large'
                    elif 'medium' in item:
                        size = 'Medium'
                    orders[session_id].append({
                        'food_item': f"Waffle Potato Fries ({size})",
                        'quantity': quantity
                    })
                    
                # Handle chicken sandwiches
                elif 'chicken sandwich' in item:
                    sandwich_name = "Chicken Sandwich"
                    if 'spicy' in item:
                        if 'deluxe' in item:
                            sandwich_name = "Spicy Deluxe Sandwich"
                        else:
                            sandwich_name = "Spicy Chicken Sandwich"
                    elif 'grilled' in item:
                        if 'club' in item:
                            sandwich_name = "Grilled Chicken Club Sandwich"
                        else:
                            sandwich_name = "Grilled Chicken Sandwich"
                    elif 'deluxe' in item:
                        sandwich_name = "Deluxe Chicken Sandwich"
                    
                    orders[session_id].append({
                        'food_item': sandwich_name,
                        'quantity': quantity
                    })
                    
                # Generic handler for other items (like salads)
                else:
                    # Remove plural 's' if present
                    clean_item = item.rstrip('s')
                    # Get the full menu item name
                    full_item_name = get_full_item_name(clean_item)
                    if full_item_name:
                        orders[session_id].append({
                            'food_item': full_item_name,
                            'quantity': quantity
                        })

            # Create order summary
            order_summary = []
            for item in orders[session_id]:
                order_summary.append(f"{item['quantity']} x {item['food_item']}")

            # Set context for additional items
            awaiting_more_items[session_id] = True
            
            if order_summary:
                response = "I've added to your order:\n" + "\n".join(order_summary)
                response += "\nWould you like anything else?"
                return create_response(response)
            else:
                return create_response("I couldn't understand the items you want to order. Could you please rephrase your order?")

        elif intent_name == 'OrderFood - size':
            size = parameters.get('size', '')
            if session_id in last_ordered_item:
                pending_item = last_ordered_item[session_id]
                food_item = pending_item['item']
                quantity = pending_item['quantity']

                full_item_name = f"{food_item} ({size})"
                order_item = {
                    'food_item': full_item_name,
                    'quantity': quantity
                }
                orders[session_id].append(order_item)
                del last_ordered_item[session_id]

                return create_response(f"I've added {quantity} {full_item_name} to your order. Would you like anything else?")

        elif intent_name == 'SpecifySize':
            size = parameters.get('Size', '')
            if session_id in last_ordered_item:
                pending_item = last_ordered_item[session_id]
                food_item = pending_item['item']
                quantity = pending_item['quantity']

                full_item_name = f"{food_item} ({size})"
                order_item = {
                    'food_item': full_item_name,
                    'quantity': quantity
                }
                orders[session_id].append(order_item)
                del last_ordered_item[session_id]

                return create_response(f"I've added {quantity} {full_item_name} to your order. Would you like anything else?")

        elif intent_name == 'ModifyOrder':
            action = parameters.get('ModifyAction', '')
            item = parameters.get('FoodItem', '')

            if action == 'remove':
                orders[session_id] = [order for order in orders[session_id]
                                      if order['food_item'] != item]
                return jsonify({
                    'fulfillmentText': f"I've removed {item} from your order."
                })
            elif action == 'clear':
                orders[session_id] = []
                return jsonify({
                    'fulfillmentText': "I've cleared your order. What would you like to order?"
                })

        elif intent_name == 'SandwichSpicyOrNot':
            # Get the original query text that contains all items
            query_text = query_result.get('queryText', '').lower()

            # Initialize pending orders for this session
            if session_id not in pending_orders:
                pending_orders[session_id] = {'items': []}

            # Parse additional items from the query
            if 'fry' in query_text or 'fries' in query_text:
                size = 'Medium'  # Default size or parse from query
                if 'large' in query_text:
                    size = 'Large'
                elif 'small' in query_text:
                    size = 'Small'
                pending_orders[session_id]['items'].append({
                    'food_item': f'Waffle Potato Fries ({size})',
                    'quantity': 1
                })

            if 'drink' in query_text:
                size = 'Medium'  # Default size or parse from query
                if 'large' in query_text:
                    size = 'Large'
                elif 'small' in query_text:
                    size = 'Small'
                pending_orders[session_id]['items'].append({
                    'food_item': f'Soft Drink ({size})',
                    'quantity': 1
                })

            return create_response("Would you like your chicken sandwich original or spicy?")

        elif intent_name == 'SandwichSpicyOrNot - custom':
            # Add the spicy sandwich
            if session_id not in orders:
                orders[session_id] = []

            order_item = {
                'food_item': 'Spicy Chicken Sandwich',
                'quantity': 1
            }
            orders[session_id].append(order_item)

            # Process any pending items
            added_items = ['Spicy Chicken Sandwich']
            if session_id in pending_orders and pending_orders[session_id].get('items'):
                for item in pending_orders[session_id]['items']:
                    orders[session_id].append(item)
                    added_items.append(item['food_item'])

                # Clear pending orders after processing
                del pending_orders[session_id]

                # Create response with all items
                items_text = ", ".join(added_items)
                return create_response(f"I've added {items_text} to your order. Would you like anything else?")

            return create_response("I've added a Spicy Chicken Sandwich to your order. Would you like anything else?")

        elif intent_name == 'SandwichSpicyOrNot - custom-2':
            order_item = {
                'food_item': 'Chicken Sandwich',
                'quantity': 1
            }
            orders[session_id].append(order_item)
            print(f"Added to order: {order_item}")
            return create_response("Sure, I have added a Chicken Sandwich to your order.")

        elif intent_name == 'ReviewOrder':
            order_items = orders.get(session_id, [])
            if not order_items:
                return jsonify({
                    'fulfillmentText': "You haven't ordered anything yet."
                })

            order_summary = ''
            for item in order_items:
                quantity = item.get('quantity', 1)
                food_item = item['food_item']
                order_summary += f"{quantity} x {food_item}\n"

            total_price = calculate_total(order_items)
            return create_response(f"Here's your current order:\n{order_summary}\nTotal: ${total_price:.2f}")

        elif intent_name == 'OrderCompletion':
            order_items = orders.get(session_id, [])
            if not order_items:
                return create_response("It seems you haven't ordered anything yet. What would you like to order?")

            # Mark this session as awaiting confirmation
            awaiting_order_confirmation[session_id] = True
            
            order_summary = ''
            for item in order_items:
                quantity = item.get('quantity', 1)
                food_item = item['food_item']
                price = price_list.get(food_item, 0)
                order_summary += f"{quantity} x {food_item} (${price:.2f} each)\n"

            total_price = calculate_total(order_items)
            return create_response(f"Thank you for your order! Here's what you ordered:\n{order_summary}\nTotal: ${total_price:.2f}\nWould you like to confirm your order?")

        elif intent_name == 'ConfirmOrder':
            # Check if we're in a menu query context
            if session_id in awaiting_menu_response:
                menu_context = awaiting_menu_response[session_id]
                item_name = menu_context['item']
                item = menu_items[item_name]
                
                if menu_context['asked_about'] == 'price':
                    # They asked about ingredients, now want price
                    awaiting_menu_response.pop(session_id)
                    return create_response(f"The {item_name} costs ${item['price']:.2f}. Would you like to order one?")
                elif menu_context['asked_about'] == 'ingredients':
                    # They asked about price, now want ingredients
                    awaiting_menu_response.pop(session_id)
                    return create_response(f"The {item_name} is made with {', '.join(item['ingredients'])}. Would you like to order one?")
            
            # Only process order confirmation if we're actually awaiting one
            elif session_id in awaiting_order_confirmation:
                order_items = orders.get(session_id, [])
                if not order_items:
                    awaiting_order_confirmation.pop(session_id, None)
                    return create_response("It seems you haven't ordered anything yet. What would you like to order?")

                # Process the confirmation
                order_summary = ''
                for item in order_items:
                    quantity = item.get('quantity', 1)
                    food_item = item['food_item']
                    order_summary += f"{quantity} x {food_item}\n"

                total_price = calculate_total(order_items)
                
                # Clear the order and confirmation status after processing
                orders[session_id] = []
                awaiting_order_confirmation.pop(session_id, None)
                
                return create_response(f"Your order has been confirmed! Here's what you ordered:\n{order_summary}\nTotal: ${total_price:.2f}\nThank you for choosing Chick-fil-A!")
            else:
                return create_response("I'm not sure what you're confirming. Would you like to place an order?")

        elif intent_name == 'Default Welcome Intent':
            return create_response("Welcome to Chick-fil-A! How can I help you today?")

        elif intent_name == 'MenuQuery':
            category = parameters.get('menucategory', '').lower()
            specific_item = parameters.get('fooditem', '')
            query_text = query_result.get('queryText', '').lower()

            # Clean up category input by removing articles
            if category:
                category = category.replace(
                    'a ', '').replace('the ', '').strip()
                # If category looks like a specific item, treat it as one
                if 'sandwich' in category or 'fries' in category or 'drink' in category:
                    specific_item = category
                    category = ''

            if specific_item:
                # Clean up specific item input by removing articles
                specific_item = specific_item.replace(
                    'a ', '').replace('the ', '').strip()

                # Handle size specification from query text
                size_match = None
                for size in ['small', 'medium', 'large']:
                    if size in query_text:
                        size_match = size.title()
                        break

                # Get full item name
                base_item_name = get_full_item_name(specific_item)
                if base_item_name:
                    if size_match:
                        full_item_name = f"{base_item_name} ({size_match})"
                    elif base_item_name in size_required_items:
                        # Default size
                        full_item_name = f"{base_item_name} (Medium)"
                    else:
                        full_item_name = base_item_name

                if full_item_name in menu_items:
                    item = menu_items[full_item_name]
                    ingredients = ', '.join(item['ingredients'])
                    price = item['price']

                    # Set the context based on what was asked
                    if any(word in query_text for word in ['price', 'cost', 'how much', 'costs']):
                        awaiting_menu_response[session_id] = {
                            'item': full_item_name,
                            'asked_about': 'ingredients'  # They asked about price, might want ingredients next
                        }
                        response = f"A {full_item_name} costs ${price:.2f}. Would you like to know about the ingredients?"
                    elif 'ingredient' in query_text or 'what' in query_text:
                        awaiting_menu_response[session_id] = {
                            'item': full_item_name,
                            'asked_about': 'price'  # They asked about ingredients, might want price next
                        }
                        response = f"Our {full_item_name} is made with {ingredients}. Would you like to know the price?"
                    else:
                        awaiting_menu_response[session_id] = {
                            'item': full_item_name,
                            'asked_about': 'order'  # They might want to order
                        }
                        response = f"Our {full_item_name} is made with {ingredients} and costs ${price:.2f}. Would you like to try it?"
                    return create_response(response)

                # If no exact match found, try partial matches
                matching_items = [item for item in menu_items.keys()
                                  if specific_item.lower() in item.lower()]
                if matching_items:
                    response = f"Let me tell you about our {specific_item} options:\n\n"
                    for item_name in matching_items:
                        item = menu_items[item_name]
                        ingredients = ', '.join(item['ingredients'])
                        price = item['price']
                        response += f"• {item_name} (${price:.2f}): Made with {ingredients}\n"
                    response += "\nWould you like to know more about any of these items?"
                    return create_response(response.strip())

                return create_response(f"I apologize, but I couldn't find any menu items matching '{specific_item}'. Would you like me to tell you about our similar items?")

            elif category:
                # Search by category
                items = get_menu_items_by_category(category)
                if items:
                    response = f"Here are our {category}:\n\n"
                    for item in items:
                        details = format_menu_item_details(item)
                        if details:
                            response += f"{details}\n\n"
                    return create_response(response.strip())
                return create_response(f"I'm sorry, I couldn't find any items in the '{category}' category.")

            # No category or item specified
            return create_response("I can tell you about our menu items. Please specify a category (like sandwiches, salads, drinks) or ask about a specific item!")

        elif intent_name == 'Yes':
            if session_id in awaiting_menu_response:
                menu_context = awaiting_menu_response[session_id]
                item_name = menu_context['item']
                item = menu_items[item_name]
                
                if menu_context['asked_about'] == 'price':
                    # They asked about ingredients, now want price
                    response = f"The {item_name} costs ${item['price']:.2f}. Would you like to order one?"
                    # Update context to order
                    awaiting_menu_response[session_id] = {
                        'item': item_name,
                        'asked_about': 'order'
                    }
                    return create_response(response)
                    
                elif menu_context['asked_about'] == 'ingredients':
                    # They asked about price, now want ingredients
                    response = f"The {item_name} is made with {', '.join(item['ingredients'])}. Would you like to order one?"
                    # Update context to order
                    awaiting_menu_response[session_id] = {
                        'item': item_name,
                        'asked_about': 'order'
                    }
                    return create_response(response)
                    
                elif menu_context['asked_about'] == 'order':
                    # They want to order the item
                    if session_id not in orders:
                        orders[session_id] = []
                    orders[session_id].append({
                        'food_item': item_name,
                        'quantity': 1
                    })
                    awaiting_menu_response.pop(session_id)  # Clear menu context
                    awaiting_more_items[session_id] = True  # Set the new context
                    return create_response(f"I've added 1 {item_name} to your order. Would you like anything else?")
            
            # If we're awaiting order confirmation, process that
            elif session_id in awaiting_order_confirmation:
                order_items = orders.get(session_id, [])
                if not order_items:
                    awaiting_order_confirmation.pop(session_id, None)
                    return create_response("It seems you haven't ordered anything yet. What would you like to order?")

                # Process the confirmation
                order_summary = ''
                for item in order_items:
                    quantity = item.get('quantity', 1)
                    food_item = item['food_item']
                    order_summary += f"{quantity} x {food_item}\n"

                total_price = calculate_total(order_items)
                
                # Clear the order and confirmation status after processing
                orders[session_id] = []
                awaiting_order_confirmation.pop(session_id, None)
                
                return create_response(f"Your order has been confirmed! Here's what you ordered:\n{order_summary}\nTotal: ${total_price:.2f}\nThank you for choosing Chick-fil-A!")

            # Default response if no context
            return create_response("I'm not sure what you're saying yes to. How can I help you?")

        elif intent_name == 'No':
            if session_id in awaiting_more_items:
                # They don't want to order anything else
                awaiting_more_items.pop(session_id)
                order_items = orders.get(session_id, [])
                if not order_items:
                    return create_response("I don't see any items in your order. What would you like to order?")
                    
                # Show order summary and ask for confirmation
                order_summary = ''
                for item in order_items:
                    quantity = item.get('quantity', 1)
                    food_item = item['food_item']
                    order_summary += f"{quantity} x {food_item}\n"
                
                total_price = calculate_total(order_items)
                awaiting_order_confirmation[session_id] = True
                return create_response(f"Here's your order summary:\n{order_summary}\nTotal: ${total_price:.2f}\nWould you like to confirm this order?")
            
            elif session_id in awaiting_menu_response:
                menu_context = awaiting_menu_response[session_id]
                item_name = menu_context['item']
                # Clear the menu context since they're not interested in more info
                awaiting_menu_response.pop(session_id)
                return create_response("No problem! Would you like to know about any other menu items?")
            
            elif session_id in awaiting_order_confirmation:
                # They don't want to confirm their order yet
                awaiting_order_confirmation.pop(session_id)
                return create_response("What else would you like to add to your order?")
            
            # If we're not in any specific context
            return create_response("What would you like to order?")

        elif intent_name:  # If we have an intent name but didn't handle it
            print(f"WARNING: Unhandled intent: {intent_name}")
            return jsonify({
                'fulfillmentText': f"Debug: Received intent '{intent_name}' but no handler found."
            })
        else:
            print("WARNING: No intent name found in request")
            return jsonify({
                'fulfillmentText': "I'm sorry, I didn't understand that. Could you please rephrase?"
            })

        print(f"Current orders after processing: {orders.get(session_id, [])}")

        # Default return at the end of the function
        return create_response("I'm processing your request. What would you like to order?")

    except Exception as e:
        print(f"Error in webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response("I encountered an error processing your request. Could you please try again?")


@app.route('/')
def index():
    return render_template('index.html')

# If you're using the Dialogflow API directly for your frontend, ensure you have the necessary setup.
# The following code is optional and only required if you're making direct API calls from your frontend.

# @app.route('/send_message', methods=['POST'])
# def send_message():
#     user_message = request.json.get('message')

#     # Send the message to Dialogflow
#     response = detect_intent_texts(
#         'your-project-id', 'unique-session-id', [user_message], 'en-US')

#     # Extract the reply
#     bot_reply = response.query_result.fulfillment_text
#     return jsonify({'reply': bot_reply})


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
