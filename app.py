from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# In-memory storage for orders
orders = {}

# Price list for menu items
price_list = {
    # Entrees
    "Chicken Sandwich": 4.29,
    "Deluxe Chicken Sandwich": 4.95,
    "Spicy Chicken Sandwich": 4.69,
    "Spicy Deluxe Sandwich": 5.25,
    "Grilled Chicken Sandwich": 5.65,
    "Grilled Chicken Club Sandwich": 7.25,
    "Nuggets (8-count)": 4.05,
    "Nuggets (12-count)": 5.95,
    "Grilled Nuggets (8-count)": 5.25,
    "Grilled Nuggets (12-count)": 7.85,
    "Chick-n-Strips (3-count)": 4.35,
    "Chick-n-Strips (4-count)": 5.19,
    "Cool Wrap": 6.75,
    "Grilled Chicken Cool Wrap": 6.79,
    # Add the rest of the menu items with their prices...
    # Salads
    "Cobb Salad": 8.19,
    "Spicy Southwest Salad": 8.19,
    "Market Salad": 8.19,
    "Side Salad": 4.09,
    # Drinks
    "Soft Drink (Small)": 1.65,
    "Soft Drink (Medium)": 1.85,
    "Soft Drink (Large)": 2.15,
    "Iced Coffee (Small)": 3.19,
    "Iced Coffee (Large)": 3.69,
    "Lemonade (Small)": 1.99,
    "Lemonade (Medium)": 2.29,
    "Lemonade (Large)": 2.69,
    "Sweet Tea (Small)": 1.65,
    "Sweet Tea (Medium)": 1.85,
    "Sweet Tea (Large)": 2.15,
    "Bottled Water": 1.79,
    # Desserts
    "Milkshake (Small)": 3.45,
    "Milkshake (Large)": 4.25,
    "Frosted Lemonade (Small)": 3.85,
    "Frosted Lemonade (Large)": 4.45,
    "Chocolate Chunk Cookie": 1.29,
    "Cookie (6-count)": 7.29,
    "Icedream Cone": 1.39,
    "Icedream Cup": 1.25,
    # ... Include all menu items
}

def calculate_total(order_items):
    total_price = 0.0
    for item in order_items:
        item_name = item['food_item']
        quantity = item.get('quantity', 1)
        item_price = price_list.get(item_name, 0.0)
        total_price += item_price * quantity
    return round(total_price, 2)

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)

    # Extract session ID to keep track of the user's session
    session_id = req.get('session')

    # Extract intent name
    intent_name = req.get('queryResult').get('intent').get('displayName')

    # Initialize order for this session if it doesn't exist
    if session_id not in orders:
        orders[session_id] = []

    def get_first(value):
        if isinstance(value, list):
            return value[0]
        return value

    if intent_name == 'OrderFood':  
        # Handle adding items to the order
        parameters = req.get('queryResult', {}).get('parameters', {})
        food_item = get_first(parameters.get('FoodItem', '')).strip()
        size = get_first(parameters.get('Size', '')).strip()
        quantity = int(get_first(parameters.get('quantity', 1)))

        # Debugging statements
        print(f"Parameters: {parameters}")
        print(f"Extracted food_item: '{food_item}'")
        print(f"Extracted size: '{size}'")
        print(f"Quantity: {quantity}")

        # Concatenate size and food item if size is provided
        if size:
            full_item_name = f"{food_item} ({size})"
        else:
            full_item_name = food_item

        # Normalize item names for matching
        full_item_name_normalized = full_item_name.lower().strip()
        price_list_normalized = {key.lower().strip(): value for key, value in price_list.items()}

        # Check if the item exists in the price list
        if full_item_name_normalized not in price_list_normalized:
            response_text = f"Sorry, we don't have {full_item_name} on the menu."
        else:
            # Get the actual item name from price_list to preserve original casing
            actual_item_name = [key for key in price_list if key.lower().strip() == full_item_name_normalized][0]
            # Add the item to the user's order
            orders[session_id].append({
                'food_item': actual_item_name,
                'quantity': quantity
            })
            response_text = f"Great! I've added {quantity} {actual_item_name} to your order. Would you like anything else?"

        return jsonify({'fulfillmentText': response_text})



    elif intent_name == 'OrderCompletion':
        # Handle order completion
        order_items = orders.get(session_id, [])
        if not order_items:
            response_text = "It seems you haven't ordered anything yet. What would you like to order?"
            return jsonify({'fulfillmentText': response_text})
        else:
            # Generate order summary text
            order_summary = ''
            for item in order_items:
                quantity = item['quantity']
                food_item = item['food_item']
                order_summary += f"{quantity} x {food_item}\n"
            order_summary = order_summary.strip()

            # Calculate total price
            total_price = calculate_total(order_items)

            response_text = f"Thank you for your order! You have ordered:\n{order_summary}\nYour total is ${total_price}. Would you like to confirm your order?"

            return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'ReviewOrder':
        # Handle order review
        order_items = orders.get(session_id, [])
        if not order_items:
            response_text = "You haven't ordered anything yet."
            return jsonify({'fulfillmentText': response_text})
        else:
            # Prepare data for custom payload
            order_details = []
            for item in order_items:
                quantity = item['quantity']
                food_item = item['food_item']
                item_price = price_list.get(food_item, 0.0)
                total_item_price = round(item_price * quantity, 2)
                order_details.append({
                    'quantity': quantity,
                    'food_item': food_item,
                    'unit_price': item_price,
                    'total_price': total_item_price
                })

            # Calculate total price
            total_price = calculate_total(order_items)

            response_text = f"Your current order total is ${total_price}. Would you like to confirm your order?"

            # Create the custom payload with actual numbers and strings
            custom_payload = {
                'order_summary': order_details,
                'total_price': total_price
            }

            # Return both the text response and the custom payload
            return jsonify({
                'fulfillmentText': response_text,
                'payload': custom_payload
            })

    elif intent_name == 'ConfirmOrder':
        # Handle order confirmation
        response_text = "Your order has been placed successfully! Thank you for choosing Chick-fil-A."
        # Clear the order
        orders.pop(session_id, None)
        return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'CancelOrder':
        # Handle order cancellation
        orders.pop(session_id, None)
        response_text = "Your order has been canceled. Let me know if you'd like to start a new order."
        return jsonify({'fulfillmentText': response_text})

    else:
        # Handle unrecognized intents
        response_text = "I'm sorry, I didn't understand that. Could you please rephrase?"
        return jsonify({'fulfillmentText': response_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
