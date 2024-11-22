from flask import Flask, request, jsonify, render_template
from static_data import price_list, item_name_mapping, size_required_items, menu_items
from flask_cors import CORS
import os
import json
import re
from google.cloud.dialogflow_v2 import SessionsClient
from google.cloud.dialogflow_v2.types import TextInput, QueryInput
from google.oauth2 import service_account
import time


# At the top of your file, after imports
app = Flask(__name__)
CORS(app)

# Global variables
dialogflow_client = None


def init_dialogflow():
    """Initialize Dialogflow client"""
    global dialogflow_client
    try:
        if os.getenv('FLASK_ENV') == 'production':
            print("Loading production credentials from environment variable")
            credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if not credentials_json:
                raise ValueError(
                    "GOOGLE_CREDENTIALS_JSON environment variable not set")

            credentials_dict = json.loads(credentials_json)
            print("Credentials loaded successfully")
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict)
        else:
            print("Loading development credentials from file")
            credentials_path = 'credentials/service-account.json'
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path)

        # Initialize Dialogflow client
        client = SessionsClient(credentials=credentials)
        print("Dialogflow client initialized successfully")
        return client

    except Exception as e:
        print(f"Error initializing credentials: {str(e)}")
        raise


# Initialize Dialogflow at startup
dialogflow_client = init_dialogflow()
print(f"Dialogflow client initialized: {dialogflow_client is not None}")


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


def create_response_message(message):
    return {
        'fulfillmentText': message,
        'fulfillmentMessages': [
            {
                'text': {
                    'text': [message]
                }
            }
        ]
    }


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


# Add at the top with other global variables
nugget_options = {
    "regular": {
        "8": "Nuggets (8-count)",
        "12": "Nuggets (12-count)"
    },
    "grilled": {
        "8": "Grilled Nuggets (8-count)",
        "12": "Grilled Nuggets (12-count)"
    }
}

# Update the HANDLED_INTENTS list at the top
HANDLED_INTENTS = [
    'OrderFood',
    'OrderFood - size',
    'SpecifySize',
    'ModifyOrder',
    'Yes',
    'No',
    'Default Welcome Intent',
    'MenuQuery',
    'OrderCompletion',
    'ReviewOrder',
    'SandwichSpicyOrNot',
    'SandwichSpicyOrNot - custom',
    'OrderNuggets',
    'NuggetType',
    'NuggetCount',
    'ClearOrder'
]

# At the top of your file, add a helper function to extract a consistent session ID


def get_consistent_session_id(session_path):
    """Extract a consistent session ID from the full session path"""
    try:
        # Extract just the web-XXXXXXXXX portion
        return session_path.split('/')[-1]
    except:
        # Fallback to a new session ID if parsing fails
        return f"web-{int(time.time() * 1000)}"


@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json()
    response_data = process_webhook(req)
    return jsonify(response_data)


def process_webhook(req):
    try:
        print("\n=== WEBHOOK REQUEST ===")

        if req is None:
            return {'fulfillmentText': "Invalid request format."}

        # Extract required data from req
        query_result = req.get('queryResult', {})
        intent = query_result.get('intent', {})
        intent_name = intent.get('displayName', '')
        query_text = query_result.get('queryText', '').lower()
        parameters = query_result.get('parameters', {})
        full_session = req.get('session', '')
        session_id = get_consistent_session_id(full_session)

        # Detailed debug logging
        print("Intent Data:", {
            'displayName': intent_name,
            'parameters': parameters,
            'queryText': query_text,
            'fulfillmentText': query_result.get('fulfillmentText', '')
        })

        print("Raw Request:", json.dumps(req, indent=2))
        print(f"Session ID: {session_id}")
        print(f"Received intent: {intent_name}")
        print(f"Query Text: {query_text}")
        print(f"Parameters: {parameters}")
        print(
            f"Current orders before processing: {orders.get(session_id, [])}")
        print(
            f"Is intent '{intent_name}' in handled intents? {intent_name in HANDLED_INTENTS}")

        # Initialize orders if needed
        if session_id not in orders:
            orders[session_id] = []

        if intent_name == 'OrderFood':
            food_items = parameters.get('FoodItem', [])
            sizes = parameters.get('Size', [])
            numbers = parameters.get('number', [])
            query = query_text.lower()

            # Initialize index for sizes
            size_idx = 0

            for idx, food_item in enumerate(food_items):
                # Map the food item name to the menu item
                mapped_item = item_name_mapping.get(food_item, food_item)

                # Determine quantity
                if idx < len(numbers) and numbers[idx]:
                    quantity = int(numbers[idx])
                else:
                    quantity = 1  # Default quantity

                # Determine if the item requires a size
                if mapped_item in size_required_items:
                    if size_idx < len(sizes):
                        size = sizes[size_idx]
                        size_idx += 1  # Move to the next size for subsequent items
                    else:
                        size = 'Medium'  # Default size
                    full_item_name = f"{mapped_item} ({size})"
                else:
                    full_item_name = mapped_item

                # Add the item to the order
                order_item = {
                    'food_item': full_item_name,
                    'quantity': quantity
                }
                orders[session_id].append(order_item)
                print(f"Added item: {full_item_name} (Quantity: {quantity})")

            # Create order summary
            order_summary = []
            for item in orders[session_id]:
                order_summary.append(
                    f"{item['quantity']} x {item['food_item']}")

            # Set context for additional items
            awaiting_more_items[session_id] = True

            if order_summary:
                response_message = "I've added to your order:\n" + \
                    "\n".join(order_summary)
                response_message += "\nWould you like anything else?"
            else:
                response_message = "I couldn't understand the items you want to order. Could you please rephrase your order?"

            return create_response_message(response_message)

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

                response_message = f"I've added {quantity} {full_item_name} to your order. Would you like anything else?"
                return create_response_message(response_message)

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

                response_message = f"I've added {quantity} {full_item_name} to your order. Would you like anything else?"
                return create_response_message(response_message)

        elif intent_name == 'OrderNuggets':
            if session_id not in awaiting_menu_response:
                awaiting_menu_response[session_id] = {}

            awaiting_menu_response[session_id] = {
                'context': 'nugget_type',
                'item': 'nuggets'
            }
            response_message = "Would you like regular or grilled nuggets?"
            return create_response_message(response_message)

        elif intent_name == 'ModifyOrder':
            print("Processing ModifyOrder intent...")
            parameters = query_result.get('parameters', {})
            actions = parameters.get('ModifyAction', [])
            items_to_remove = parameters.get('ItemsToRemove', '')
            items_to_add = parameters.get('ItemsToAdd', [])
            food_items = parameters.get('FoodItem', [])

            print(
                f"Debug - Actions: {actions}, Remove: {items_to_remove}, Add: {items_to_add}, FoodItems: {food_items}")

            # If we have a remove action and FoodItem but no ItemsToRemove, use FoodItem
            if 'remove' in actions and food_items and not items_to_remove:
                items_to_remove = food_items

            # Ensure lists
            items_to_remove = [items_to_remove] if isinstance(
                items_to_remove, str) else items_to_remove
            items_to_add = [items_to_add] if isinstance(
                items_to_add, str) else items_to_add

            print(f"Debug - Final items to remove: {items_to_remove}")
            print(f"Debug - Final items to add: {items_to_add}")

            # Handle removals
            if 'remove' in actions and items_to_remove:
                original_order = orders[session_id].copy()
                orders[session_id] = []
                items_removed = []

                for order_item in original_order:
                    should_keep = True
                    for item_to_remove in items_to_remove:
                        if isinstance(item_to_remove, str) and item_to_remove.strip():
                            remove_name = item_to_remove.lower().strip()
                            order_name = order_item['food_item'].lower(
                            ).strip()

                            print(
                                f"Debug - Comparing: '{remove_name}' with '{order_name}'")

                            if ('fries' in remove_name and 'fries' in order_name) or \
                               ('drink' in remove_name and 'drink' in order_name) or \
                               (remove_name in order_name):
                                should_keep = False
                                items_removed.append(order_item['food_item'])
                                break

                    if should_keep:
                        orders[session_id].append(order_item)

            # Handle additions
            if 'add' in actions and items_to_add:
                for item_to_add in items_to_add:
                    if isinstance(item_to_add, str) and item_to_add.strip():
                        orders[session_id].append({
                            'food_item': item_to_add,
                            'quantity': 1
                        })

            print(f"Debug - Final order: {orders[session_id]}")

            # Prepare response
            response_parts = []
            if items_removed:
                response_parts.append(
                    f"I've removed {', '.join(items_removed)} from your order")
            if items_to_add:
                response_parts.append(
                    f"I've added {', '.join(items_to_add)} to your order")

            response = f"{' and '.join(response_parts)}. Would you like anything else?"
            if not response_parts:
                response = "I couldn't understand what you wanted to modify. Please try again."

            return create_response(response)

        elif intent_name == 'SandwichSpicyOrNot':
            if session_id not in awaiting_menu_response:
                awaiting_menu_response[session_id] = {}

            awaiting_menu_response[session_id] = {
                'context': 'sandwich_spicy',
                'asked_about': 'spicy'
            }
            response_message = "Would you like your chicken sandwich spicy or regular?"
            return create_response_message(response_message)

        elif intent_name == 'SandwichSpicyOrNot - custom':
            response = query_text.lower()
            if session_id not in orders:
                orders[session_id] = []

            if 'spicy' in response:
                orders[session_id].append({
                    'food_item': 'Spicy Chicken Sandwich',
                    'quantity': 1
                })
            else:
                orders[session_id].append({
                    'food_item': 'Chicken Sandwich',
                    'quantity': 1
                })

            awaiting_more_items[session_id] = True
            response_message = "I've added your sandwich to the order. Would you like anything else?"
            return create_response_message(response_message)

        elif intent_name == 'ReviewOrder':
            order_items = orders.get(session_id, [])
            if not order_items:
                response_message = "You haven't ordered anything yet."
                return create_response_message(response_message)

            order_summary = ''
            for item in order_items:
                quantity = item.get('quantity', 1)
                food_item = item['food_item']
                order_summary += f"{quantity} x {food_item}\n"

            total_price = calculate_total(order_items)
            response_message = f"Here's your current order:\n{order_summary}\nTotal: ${total_price:.2f}"
            return create_response_message(response_message)

        elif intent_name == 'OrderCompletion':
            order_items = orders.get(session_id, [])
            if not order_items:
                response_message = "It seems you haven't ordered anything yet. What would you like to order?"
                return create_response_message(response_message)

            # Mark this session as awaiting confirmation
            awaiting_order_confirmation[session_id] = True

            order_summary = ''
            for item in order_items:
                quantity = item.get('quantity', 1)
                food_item = item['food_item']
                price = price_list.get(food_item, 0)
                order_summary += f"{quantity} x {food_item} (${price:.2f} each)\n"

            total_price = calculate_total(order_items)
            response_message = (
                f"Thank you for your order! Here's what you ordered:\n{order_summary}"
                f"\nTotal: ${total_price:.2f}\nWould you like to confirm your order?"
            )
            return create_response_message(response_message)

        elif intent_name == 'ConfirmOrder':
            # Check if we're in a menu query context
            if session_id in awaiting_menu_response:
                menu_context = awaiting_menu_response[session_id]
                item_name = menu_context['item']
                item = menu_items[item_name]

                if menu_context['asked_about'] == 'price':
                    # They asked about ingredients, now want price
                    awaiting_menu_response.pop(session_id)
                    response_message = f"The {item_name} costs ${item['price']:.2f}. Would you like to order one?"
                    return create_response_message(response_message)
                elif menu_context['asked_about'] == 'ingredients':
                    # They asked about price, now want ingredients
                    awaiting_menu_response.pop(session_id)
                    response_message = f"The {item_name} is made with {', '.join(item['ingredients'])}. Would you like to order one?"
                    return create_response_message(response_message)

            # Only process order confirmation if we're actually awaiting one
            elif session_id in awaiting_order_confirmation:
                order_items = orders.get(session_id, [])
                if not order_items:
                    awaiting_order_confirmation.pop(session_id, None)
                    response_message = "It seems you haven't ordered anything yet. What would you like to order?"
                    return create_response_message(response_message)

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

                response_message = (
                    f"Your order has been confirmed! Here's what you ordered:\n{order_summary}"
                    f"\nTotal: ${total_price:.2f}\nThank you for choosing Chick-fil-A!"
                )
                return create_response_message(response_message)
            else:
                response_message = "I'm not sure what you're confirming. Would you like to place an order?"
                return create_response_message(response_message)

        elif intent_name == 'Default Welcome Intent':
            response_message = "Welcome to Chick-fil-A! How can I help you today?"
            return create_response_message(response_message)

        elif intent_name == 'MenuQuery':
            menu_category = parameters.get('menucategory', '').lower()
            food_item = parameters.get('fooditem', '')

            # If a specific item was asked about
            if food_item:
                if food_item in menu_items:
                    ingredients = menu_items[food_item]['ingredients']
                    price = menu_items[food_item]['price']

                    awaiting_menu_response[session_id] = {
                        'item': food_item,
                        'asked_about': 'ingredients'
                    }

                    response_message = f"{food_item} contains: {', '.join(ingredients)}. Would you like to know the price?"
                    return create_response_message(response_message)

            # If a specific category was requested
            elif menu_category:
                items = get_menu_items_by_category(menu_category)
                if items:
                    items_text = ", ".join(items)
                    response_message = f"Here are our {menu_category} options: {items_text}"
                    return create_response_message(response_message)
                else:
                    response_message = f"I'm sorry, I don't have information about {menu_category}."
                    return create_response_message(response_message)

            # If no specific category or item was mentioned
            else:
                categories = list(menu_items.keys())
                categories_text = ", ".join(categories)
                response_message = f"We have several menu categories: {categories_text}. Which would you like to know more about?"
                return create_response_message(response_message)

        elif intent_name == 'Yes':
            # Check if we're awaiting order confirmation
            if session_id in awaiting_order_confirmation:
                order_items = orders.get(session_id, [])
                if not order_items:
                    awaiting_order_confirmation.pop(session_id)
                    response_message = "It seems you haven't ordered anything yet. What would you like to order?"
                    return create_response_message(response_message)

                # Process the confirmation
                order_summary = ''
                for item in order_items:
                    quantity = item.get('quantity', 1)
                    food_item = item['food_item']
                    order_summary += f"{quantity} x {food_item}\n"

                total_price = calculate_total(order_items)

                # Clear the order and confirmation status after processing
                orders[session_id] = []
                awaiting_order_confirmation.pop(session_id)

                response_message = (
                    f"Your order has been confirmed! Here's what you ordered:\n{order_summary}"
                    f"\nTotal: ${total_price:.2f}\nThank you for choosing Chick-fil-A!"
                )
                return create_response_message(response_message)

            # Handle other Yes responses (menu queries, etc.)
            elif session_id in awaiting_menu_response:
                menu_context = awaiting_menu_response[session_id]
                item_name = menu_context['item']

                if menu_context['asked_about'] == 'ingredients':
                    # They asked about ingredients, now want price
                    price = price_list.get(item_name, "price not available")
                    response_message = f"The {item_name} costs ${price:.2f}. Would you like to order one?"
                    # Update context to order
                    awaiting_menu_response[session_id] = {
                        'item': item_name,
                        'asked_about': 'order'
                    }
                    return create_response_message(response_message)

                elif menu_context['asked_about'] == 'order':
                    # They want to order the item
                    if session_id not in orders:
                        orders[session_id] = []
                    orders[session_id].append({
                        'food_item': item_name,
                        'quantity': 1
                    })
                    awaiting_menu_response.pop(
                        session_id)  # Clear menu context
                    # Set the new context
                    awaiting_more_items[session_id] = True
                    response_message = f"I've added 1 {item_name} to your order. Would you like anything else?"
                    return create_response_message(response_message)

        elif intent_name == 'No':
            if session_id in awaiting_more_items:
                # They don't want more items, proceed to order completion
                awaiting_more_items.pop(session_id)
                order_items = orders.get(session_id, [])
                if not order_items:
                    response_message = "I don't see any items in your order. Would you like to order something?"
                    return create_response_message(response_message)

                # Generate order summary
                order_summary = ''
                for item in order_items:
                    quantity = item.get('quantity', 1)
                    food_item = item['food_item']
                    order_summary += f"{quantity} x {food_item}\n"

                total_price = calculate_total(order_items)
                awaiting_order_confirmation[session_id] = True

                response_message = (
                    f"Here's your order summary:\n{order_summary}\n"
                    f"Total: ${total_price:.2f}\n"
                    "Would you like to confirm this order?"
                )
                return create_response_message(response_message)
            else:
                response_message = "I'm not sure what you're saying no to. Would you like to place an order?"
                return create_response_message(response_message)

        elif intent_name == 'NuggetType':
            nugget_type = query_text.lower()
            if session_id not in awaiting_menu_response:
                awaiting_menu_response[session_id] = {}

            print(f"Processing nugget type: {nugget_type}")
            awaiting_menu_response[session_id] = {
                'context': 'nugget_count',
                'nugget_type': 'regular' if 'regular' in nugget_type else 'grilled'
            }
            response_message = "Would you like an 8-count or 12-count?"
            return create_response_message(response_message)

        elif intent_name == 'NuggetCount':
            if session_id in awaiting_menu_response and awaiting_menu_response[session_id].get('context') == 'nugget_count':
                count = '12' if '12' in query_text else '8'
                nugget_type = awaiting_menu_response[session_id].get(
                    'nugget_type', 'regular')

                # Get the correct nugget item name
                nugget_item = nugget_options[nugget_type][count]

                # Add to orders
                orders[session_id].append({
                    'food_item': nugget_item,
                    'quantity': 1
                })

                # Clear nugget context and set awaiting more items
                awaiting_menu_response.pop(session_id)
                awaiting_more_items[session_id] = True

                print(f"Added nuggets to order: {nugget_item}")
                response_message = f"I've added {nugget_item} to your order. Would you like anything else?"
                return create_response_message(response_message)
            else:
                return create_response("I'm not sure what type of nuggets you'd like. Would you like regular or grilled nuggets?")

        elif intent_name == 'ClearOrder':
            if session_id in orders and orders[session_id]:
                orders[session_id] = []  # Clear the order
                clear_session_data(session_id)  # Clear all session data
                return create_response("I've cleared your order. What would you like to order?")
            return create_response("You don't have any items in your order. Would you like to start a new order?")

        elif intent_name:  # If we have an intent name but didn't handle it
            print(f"WARNING: Unhandled intent: {intent_name}")
            response_message = f"Debug: Received intent '{intent_name}' but no handler found."
            return create_response_message(response_message)
        else:
            print("WARNING: No intent name found in request")
            response_message = "I'm sorry, I didn't understand that. Could you please rephrase?"
            return create_response_message(response_message)

    except Exception as e:
        print(f"Error in process_webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'fulfillmentText': "I encountered an error processing your request. Could you please try again?"
        }

    except Exception as e:
        print(f"Error in process_webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'fulfillmentText': "I encountered an error processing your request. Could you please try again?"
        }


@app.route('/dialogflow', methods=['POST'])
def handle_dialogflow():
    try:
        data = request.get_json(silent=True, force=True)

        if 'sessionId' in data and 'text' in data:  # Direct text input
            session_id = data.get('sessionId')
            user_text = data.get('text')

            session = app.dialogflow_client.session_path(
                'fast-food-chatbot', session_id)
            text_input = TextInput(text=user_text, language_code='en')
            query_input = QueryInput(text=text_input)

            response = app.dialogflow_client.detect_intent(
                request={'session': session, 'query_input': query_input}
            )

            # Convert parameters to JSON-serializable format
            def convert_proto_value(value):
                if hasattr(value, 'values'):  # RepeatedComposite
                    return [str(v) for v in value.values]
                elif hasattr(value, 'fields'):  # MapComposite
                    return {k: convert_proto_value(v) for k, v in value.fields.items()}
                return str(value) if value else []

            parameters = {k: convert_proto_value(
                v) for k, v in response.query_result.parameters.items()}

            return jsonify({
                'fulfillmentText': response.query_result.fulfillment_text,
                'intent': response.query_result.intent.display_name,
                'parameters': parameters,
                'queryText': response.query_result.query_text
            })
        elif 'queryResult' in data:  # Webhook request
            return process_webhook_request(data)
        else:
            return jsonify({
                'fulfillmentText': "Invalid request format"
            }), 400

    except Exception as e:
        print(f"Error in handle_dialogflow: {str(e)}")
        return jsonify({
            'error': str(e),
            'fulfillmentText': "I encountered an error processing your request. Could you please try again?"
        }), 500


def process_webhook_request(req):
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
        full_session = req.get('session', '')
        session_id = get_consistent_session_id(req.get('session', ''))
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
        print(
            f"Is intent '{intent_name}' in handled intents? {intent_name in HANDLED_INTENTS}")

        if intent_name == 'OrderFood':
            food_items = parameters.get('FoodItem', [])
            default_size = parameters.get('Size', 'Medium')
            query = query_text.lower()

            if session_id not in orders:
                orders[session_id] = []

            added_items = []

            # Split query into individual items and clean up
            query = re.sub(r'^can i get |^can i have |^i want ', '', query)
            query = query.replace(',', ' and ')
            items = [item.strip() for item in query.split(' and ')]

            print(f"Processing items: {items}")

            # Process each item in the query
            for item in items:
                item_size = default_size  # Start with default size
                item_quantity = 1     # Default quantity
                original_item = item  # Keep original item text for reference

                # Extract quantity
                quantity_match = re.match(r'^(\d+)', item)
                if quantity_match:
                    item_quantity = int(quantity_match.group(1))
                    item = item[len(quantity_match.group(0)):].strip()

                # Extract size from the item text
                size_match = re.search(
                    r'(small|medium|large)', item, re.IGNORECASE)
                if size_match:
                    item_size = size_match.group(1).capitalize()
                    item = item.replace(size_match.group(1), '').strip()

                print(
                    f"Processing: {original_item} -> Quantity: {item_quantity}, Size: {item_size}")

                # Match item to menu items
                matched_item = None
                if 'fry' in item or 'fries' in item:
                    matched_item = 'Waffle Fries'
                    full_item_name = f"Waffle Potato Fries ({item_size})"
                elif 'drink' in item or 'soda' in item or 'beverage' in item:
                    matched_item = 'Soft Drink'
                    full_item_name = f"Soft Drink ({item_size})"
                elif 'milkshake' in item or 'shake' in item:
                    matched_item = 'Milkshake'
                    full_item_name = f"Milkshake ({item_size})"
                elif 'lemonade' in item:
                    matched_item = 'Lemonade'
                    full_item_name = f"Lemonade ({item_size})"
                elif 'tea' in item:
                    matched_item = 'Iced Tea'
                    full_item_name = f"Iced Tea ({item_size})"
                else:
                    # For non-size items, use the FoodItem from parameters
                    for food_item in food_items:
                        if food_item.lower() in item.lower():
                            matched_item = food_item
                            full_item_name = food_item
                            break

                if matched_item:
                    orders[session_id].append({
                        'food_item': full_item_name,
                        'quantity': item_quantity
                    })
                    added_items.append(
                        f"{item_quantity} {full_item_name}" if item_quantity > 1 else full_item_name)
                    print(
                        f"Added item: {full_item_name} (Quantity: {item_quantity})")

            if added_items:
                items_text = ", ".join(added_items)
                awaiting_more_items[session_id] = True
                return create_response(f"I've added {items_text} to your order. Would you like anything else?")

            return create_response("I didn't catch what food item you wanted. Could you please repeat that?")

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

        elif intent_name == 'OrderNuggets':
            if session_id not in awaiting_menu_response:
                awaiting_menu_response[session_id] = {}

            awaiting_menu_response[session_id] = {
                'context': 'nugget_type',
                'item': 'nuggets'
            }
            return create_response("Would you like regular or grilled nuggets?")

        elif intent_name == 'ModifyOrder':
            print("Processing ModifyOrder intent...")
            parameters = query_result.get('parameters', {})
            actions = parameters.get('ModifyAction', [])
            items_to_remove = parameters.get('ItemsToRemove', '')
            items_to_add = parameters.get('ItemsToAdd', [])
            food_items = parameters.get('FoodItem', [])

            print(
                f"Debug - Actions: {actions}, Remove: {items_to_remove}, Add: {items_to_add}, FoodItems: {food_items}")

            # If we have a remove action and FoodItem but no ItemsToRemove, use FoodItem
            if 'remove' in actions and food_items and not items_to_remove:
                items_to_remove = food_items

            # Ensure lists
            items_to_remove = [items_to_remove] if isinstance(
                items_to_remove, str) else items_to_remove
            items_to_add = [items_to_add] if isinstance(
                items_to_add, str) else items_to_add

            print(f"Debug - Final items to remove: {items_to_remove}")
            print(f"Debug - Final items to add: {items_to_add}")

            # Handle removals
            if 'remove' in actions and items_to_remove:
                original_order = orders[session_id].copy()
                orders[session_id] = []
                items_removed = []

                for order_item in original_order:
                    should_keep = True
                    for item_to_remove in items_to_remove:
                        if isinstance(item_to_remove, str) and item_to_remove.strip():
                            remove_name = item_to_remove.lower().strip()
                            order_name = order_item['food_item'].lower(
                            ).strip()

                            print(
                                f"Debug - Comparing: '{remove_name}' with '{order_name}'")

                            if ('fries' in remove_name and 'fries' in order_name) or \
                               ('drink' in remove_name and 'drink' in order_name) or \
                               (remove_name in order_name):
                                should_keep = False
                                items_removed.append(order_item['food_item'])
                                break

                    if should_keep:
                        orders[session_id].append(order_item)

            # Handle additions
            if 'add' in actions and items_to_add:
                for item_to_add in items_to_add:
                    if isinstance(item_to_add, str) and item_to_add.strip():
                        orders[session_id].append({
                            'food_item': item_to_add,
                            'quantity': 1
                        })

            print(f"Debug - Final order: {orders[session_id]}")

            # Prepare response
            response_parts = []
            if items_removed:
                response_parts.append(
                    f"I've removed {', '.join(items_removed)} from your order")
            if items_to_add:
                response_parts.append(
                    f"I've added {', '.join(items_to_add)} to your order")

            response = f"{' and '.join(response_parts)}. Would you like anything else?"
            if not response_parts:
                response = "I couldn't understand what you wanted to modify. Please try again."

            return create_response(response)

        elif intent_name == 'SandwichSpicyOrNot':
            if session_id not in awaiting_menu_response:
                awaiting_menu_response[session_id] = {}

            awaiting_menu_response[session_id] = {
                'context': 'sandwich_spicy',
                'asked_about': 'spicy'
            }
            return create_response("Would you like your chicken sandwich spicy or regular?")

        elif intent_name == 'SandwichSpicyOrNot - custom':
            response = query_text.lower()
            if session_id not in orders:
                orders[session_id] = []

            if 'spicy' in response:
                orders[session_id].append({
                    'food_item': 'Spicy Chicken Sandwich',
                    'quantity': 1
                })
            else:
                orders[session_id].append({
                    'food_item': 'Chicken Sandwich',
                    'quantity': 1
                })

            awaiting_more_items[session_id] = True
            return create_response("I've added your sandwich to the order. Would you like anything else?")

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
            menu_category = parameters.get('menucategory', '').lower()
            food_item = parameters.get('fooditem', '')

            # If a specific item was asked about
            if food_item:
                if food_item in menu_items:
                    ingredients = menu_items[food_item]['ingredients']
                    price = menu_items[food_item]['price']

                    awaiting_menu_response[session_id] = {
                        'item': food_item,
                        'asked_about': 'ingredients'
                    }

                    return create_response(f"{food_item} contains: {', '.join(ingredients)}. Would you like to know the price?")

            # If a specific category was requested
            elif menu_category:
                items = get_menu_items_by_category(menu_category)
                if items:
                    items_text = ", ".join(items)
                    return create_response(f"Here are our {menu_category} options: {items_text}")
                else:
                    return create_response(f"I'm sorry, I don't have information about {menu_category}.")

            # If no specific category or item was mentioned
            else:
                categories = list(menu_items.keys())
                categories_text = ", ".join(categories)
                return create_response(f"We have several menu categories: {categories_text}. Which would you like to know more about?")

        elif intent_name == 'Yes':
            # Check if we're awaiting order confirmation
            if session_id in awaiting_order_confirmation:
                order_items = orders.get(session_id, [])
                if not order_items:
                    awaiting_order_confirmation.pop(session_id)
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
                awaiting_order_confirmation.pop(session_id)

                return create_response(f"Your order has been confirmed! Here's what you ordered:\n{order_summary}\nTotal: ${total_price:.2f}\nThank you for choosing Chick-fil-A!")

            # Handle other Yes responses (menu queries, etc.)
            elif session_id in awaiting_menu_response:
                menu_context = awaiting_menu_response[session_id]
                item_name = menu_context['item']

                if menu_context['asked_about'] == 'ingredients':
                    # They asked about ingredients, now want price
                    price = price_list.get(item_name, "price not available")
                    response = f"The {item_name} costs ${price:.2f}. Would you like to order one?"
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
                    awaiting_menu_response.pop(
                        session_id)  # Clear menu context
                    # Set the new context
                    awaiting_more_items[session_id] = True
                    return create_response(f"I've added 1 {item_name} to your order. Would you like anything else?")

        elif intent_name == 'No':
            if session_id in awaiting_more_items:
                # They don't want more items, proceed to order completion
                awaiting_more_items.pop(session_id)
                order_items = orders.get(session_id, [])
                if not order_items:
                    return create_response("I don't see any items in your order. Would you like to order something?")

                # Generate order summary
                order_summary = ''
                for item in order_items:
                    quantity = item.get('quantity', 1)
                    food_item = item['food_item']
                    order_summary += f"{quantity} x {food_item}\n"

                total_price = calculate_total(order_items)
                awaiting_order_confirmation[session_id] = True

                return create_response(
                    f"Here's your order summary:\n{order_summary}\n"
                    f"Total: ${total_price:.2f}\n"
                    "Would you like to confirm this order?"
                )
            else:
                return create_response("I'm not sure what you're saying no to. Would you like to place an order?")

        elif intent_name == 'NuggetType':
            nugget_type = query_text.lower()
            if session_id not in awaiting_menu_response:
                awaiting_menu_response[session_id] = {}

            print(f"Processing nugget type: {nugget_type}")
            awaiting_menu_response[session_id] = {
                'context': 'nugget_count',
                'nugget_type': 'regular' if 'regular' in nugget_type else 'grilled'
            }
            return create_response("Would you like an 8-count or 12-count?")

        elif intent_name == 'NuggetCount':
            if session_id in awaiting_menu_response and awaiting_menu_response[session_id].get('context') == 'nugget_count':
                count = '12' if '12' in query_text else '8'
                nugget_type = awaiting_menu_response[session_id].get(
                    'nugget_type', 'regular')

                # Get the correct nugget item name
                nugget_item = nugget_options[nugget_type][count]

                # Initialize orders if needed
                if session_id not in orders:
                    orders[session_id] = []

                # Add to orders
                orders[session_id].append({
                    'food_item': nugget_item,
                    'quantity': 1
                })

                # Clear nugget context and set awaiting more items
                awaiting_menu_response.pop(session_id)
                awaiting_more_items[session_id] = True

                print(f"Added nuggets to order: {nugget_item}")
                return create_response(f"I've added {nugget_item} to your order. Would you like anything else?")
            else:
                return create_response("I'm not sure what type of nuggets you'd like. Would you like regular or grilled nuggets?")

        elif intent_name == 'ClearOrder':
            if session_id in orders and orders[session_id]:
                orders[session_id] = []  # Clear the order
                clear_session_data(session_id)  # Clear all session data
                return create_response("I've cleared your order. What would you like to order?")
            return create_response("You don't have any items in your order. Would you like to start a new order?")

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
def home():
    # Generate a unique session ID
    session_id = f"web-{int(time.time() * 1000)}"
    return render_template('index1.html', session_id=session_id)

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
