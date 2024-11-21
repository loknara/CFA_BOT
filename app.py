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

# Add a function to clear orders for a session
def clear_session_data(session_id):
    if session_id in orders:
        del orders[session_id]
    if session_id in pending_orders:
        del pending_orders[session_id]
    if session_id in last_ordered_item:
        del last_ordered_item[session_id]

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
            'Default Welcome Intent'
        ]
        print(
            f"Is intent '{intent_name}' in handled intents? {intent_name in HANDLED_INTENTS}")

        if intent_name == 'OrderFood':
            query_text = query_result.get('queryText', '').lower()
            
            if session_id not in orders:
                orders[session_id] = []

            # Split the order text into individual items
            order_parts = []
            # First split by comma and 'and'
            main_parts = re.split(r',|(?:\s+and\s+)', query_text)
            for part in main_parts:
                part = part.strip()
                if part:
                    # Remove common prefixes like "can i get", "i want", etc.
                    part = re.sub(r'^(?:can\s+i\s+get|i\s+want|get\s+me|give\s+me)\s+', '', part)
                    order_parts.append(part.strip())

            # Process each part of the order
            for part in order_parts:
                # Extract quantity
                quantity = 1
                quantity_match = re.search(r'(\d+)', part)
                if quantity_match:
                    quantity = int(quantity_match.group(1))
                elif 'a ' in part or 'an ' in part:
                    quantity = 1
                
                # Extract size
                size = None
                if 'small' in part:
                    size = 'Small'
                elif 'medium' in part:
                    size = 'Medium'
                elif 'large' in part:
                    size = 'Large'
                
                # Process spicy chicken sandwich
                if 'spicy' in part and ('sandwich' in part or 'chicken' in part):
                    orders[session_id].append({
                        'food_item': 'Spicy Chicken Sandwich',
                        'quantity': quantity
                    })
                
                # Process fries
                elif 'fry' in part or 'fries' in part:
                    size = size or 'Medium'  # Default to medium if no size specified
                    orders[session_id].append({
                        'food_item': f'Waffle Potato Fries ({size})',
                        'quantity': quantity
                    })
                
                # Process drinks (including variations like 'coke', 'drink', etc.)
                elif any(drink in part for drink in ['drink', 'coke', 'sprite', 'beverage']):
                    size = size or 'Medium'  # Default to medium if no size specified
                    orders[session_id].append({
                        'food_item': f'Soft Drink ({size})',
                        'quantity': quantity
                    })

            # Create response with all items
            if orders[session_id]:
                added_items = []
                for item in orders[session_id]:
                    item_text = f"{item['quantity']} {item['food_item']}"
                    added_items.append(item_text)
                
                response_text = "I've added " + ", ".join(added_items) + " to your order. Would you like anything else?"
                return create_response(response_text)
            else:
                return create_response("I didn't catch that. Could you please repeat your order?")

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
                return jsonify({
                    'fulfillmentText': "It seems you haven't ordered anything yet. What would you like to order?"
                })

            order_summary = ''
            for item in order_items:
                quantity = item.get('quantity', 1)
                food_item = item['food_item']
                price = price_list.get(food_item, 0)
                order_summary += f"{quantity} x {food_item} (${price:.2f} each)\n"

            total_price = calculate_total(order_items)
            return create_response(f"Thank you for your order! Here's what you ordered:\n{order_summary}\nTotal: ${total_price:.2f}\nWould you like to confirm your order?")

        elif intent_name == 'ConfirmOrder':
            # Handle order confirmation
            order_items = orders.get(session_id, [])
            if not order_items:
                return jsonify({
                    'fulfillmentText': "It seems you haven't ordered anything yet. What would you like to order?"
                })

            # Confirm the order
            order_summary = ''
            for item in order_items:
                quantity = item.get('quantity', 1)
                food_item = item['food_item']
                order_summary += f"{quantity} x {food_item}\n"

            total_price = calculate_total(order_items)
            # Clear the order after confirmation
            orders[session_id] = []
            return create_response(f"Your order has been confirmed! Here's what you ordered:\n{order_summary}\nTotal: ${total_price:.2f}\nThank you for choosing Chick-fil-A!")

        elif intent_name == 'Default Welcome Intent':
            return create_response("Welcome to Chick-fil-A! How can I help you today?")

        elif intent_name == 'MenuInquiry':
            item = parameters.get('FoodItem', '')
            inquiry_type = parameters.get('InquiryType', '')
            
            if inquiry_type == 'price':
                price = price_list.get(item, 0)
                return jsonify({
                    'fulfillmentText': f"The {item} costs ${price:.2f}"
                })
            # Add more inquiry types as needed

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
