from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)

# In-memory storage for orders and last ordered item per session
orders = {}
last_ordered_item = {}

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
    "Chick-fil-A Cool Wrap": 6.75,
    "Grilled Cool Wrap": 6.79,

    # Salads
    "Cobb Salad": 8.19,
    "Spicy Southwest Salad": 8.19,
    "Market Salad": 8.19,
    "Side Salad": 4.09,

    # Sides
    "Waffle Potato Fries (Small)": 1.89,
    "Waffle Potato Fries (Medium)": 2.15,
    "Waffle Potato Fries (Large)": 2.45,
    "Mac & Cheese (Small)": 2.99,
    "Mac & Cheese (Medium)": 3.55,
    "Mac & Cheese (Large)": 5.25,
    "Fruit Cup (Small)": 2.85,
    "Fruit Cup (Medium)": 3.25,
    "Fruit Cup (Large)": 4.25,
    "Chicken Noodle Soup (Small)": 2.65,
    "Chicken Noodle Soup (Large)": 4.65,
    "Greek Yogurt Parfait": 3.45,
    "Side of Kale Crunch": 1.85,
    "Waffle Potato Chips": 1.89,

    # Beverages
    "Freshly-Brewed Iced Tea Sweetened (Small)": 1.65,
    "Freshly-Brewed Iced Tea Sweetened (Medium)": 1.85,
    "Freshly-Brewed Iced Tea Sweetened (Large)": 2.15,
    "Freshly-Brewed Iced Tea Unsweetened (Small)": 1.65,
    "Freshly-Brewed Iced Tea Unsweetened (Medium)": 1.85,
    "Freshly-Brewed Iced Tea Unsweetened (Large)": 2.15,
    "Chick-fil-A Lemonade (Small)": 1.99,
    "Chick-fil-A Lemonade (Medium)": 2.29,
    "Chick-fil-A Lemonade (Large)": 2.69,
    "Chick-fil-A Diet Lemonade (Small)": 1.99,
    "Chick-fil-A Diet Lemonade (Medium)": 2.29,
    "Chick-fil-A Diet Lemonade (Large)": 2.69,
    "Soft Drink (Small)": 1.65,
    "Soft Drink (Medium)": 1.85,
    "Soft Drink (Large)": 2.15,
    "1% Chocolate Milk": 1.29,
    "1% White Milk": 1.29,
    "Simply Orange Juice": 2.25,
    "Bottled Water": 1.79,
    "Coffee": 1.65,
    "Iced Coffee (Small)": 2.69,
    "Iced Coffee (Large)": 3.09,
    "Sunjoy (Small)": 1.99,
    "Sunjoy (Medium)": 2.29,
    "Sunjoy (Large)": 2.69,

    # Treats
    "Frosted Lemonade (Small)": 3.85,
    "Frosted Lemonade (Large)": 4.45,
    "Frosted Coffee (Small)": 3.85,
    "Frosted Coffee (Large)": 4.45,
    "Milkshake (Small)": 3.45,
    "Milkshake (Large)": 4.25,
    "Peppermint Chocolate Chip Milkshake (Small)": 3.65,
    "Peppermint Chocolate Chip Milkshake (Large)": 4.45,
    "Chocolate Chunk Cookie": 1.29,
    "Chocolate Chunk Cookie (6-count)": 7.29,
    "Icedream Cone": 1.39,
    "Icedream Cup": 1.25,
    "Chocolate Fudge Brownie": 1.89,

    # Kid's Meals
    "Nuggets Kid's Meal (4-count)": 3.35,
    "Nuggets Kid's Meal (6-count)": 4.05,
    "Grilled Nuggets Kid's Meal (4-count)": 3.75,
    "Grilled Nuggets Kid's Meal (6-count)": 4.45,
    "Chick-n-Strips Kid's Meal (1-count)": 3.25,
    "Chick-n-Strips Kid's Meal (2-count)": 3.95,

    # Breakfast Items
    "Chick-fil-A Chicken Biscuit": 3.09,
    "Spicy Chicken Biscuit": 3.29,
    "Chick-n-Minis (4-count)": 4.49,
    "Egg White Grill": 4.35,
    "Hash Brown Scramble Burrito": 3.75,
    "Hash Brown Scramble Bowl": 4.65,
    "Sausage Biscuit": 2.19,
    "Bacon, Egg & Cheese Biscuit": 3.59,
    "Sausage, Egg & Cheese Biscuit": 3.79,
    "Chicken, Egg & Cheese Bagel": 4.79,
    "Hash Browns": 1.09,
    "Greek Yogurt Parfait (Breakfast)": 3.45,
    "Fruit Cup (Breakfast, Small)": 2.85,

    # Sauces and Dressings (if applicable)
    "Chick-fil-A Sauce": 0.00,
    "Polynesian Sauce": 0.00,
    "Garden Herb Ranch Sauce": 0.00,
    "Zesty Buffalo Sauce": 0.00,
    "Honey Mustard Sauce": 0.00,
    "Barbeque Sauce": 0.00,
    "Sweet and Spicy Sriracha Sauce": 0.00,
    "Honey Roasted BBQ Sauce": 0.00,

    # Dressings
    "Avocado Lime Ranch Dressing": 0.00,
    "Fat-Free Honey Mustard Dressing": 0.00,
    "Garden Herb Ranch Dressing": 0.00,
    "Light Balsamic Vinaigrette Dressing": 0.00,
    "Light Italian Dressing": 0.00,
    "Zesty Apple Cider Vinaigrette Dressing": 0.00,
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
            if value:
                return value[0]
            else:
                return ''
        return value

    if intent_name == 'OrderFood':
        # Handle adding items to the order
        parameters = req.get('queryResult', {}).get('parameters', {})
        food_item = get_first(parameters.get('FoodItem', '')).strip()
        size = get_first(parameters.get('Size', '')).strip()
        count = get_first(parameters.get('Count', '')).strip()
        quantity = get_first(parameters.get('number', 1))
        if quantity:
            quantity = int(quantity)
        else:
            quantity = 1

        # Debugging statements
        print(f"Intent: {intent_name}")
        print(f"Parameters: {parameters}")
        print(f"Extracted food_item: '{food_item}'")
        print(f"Extracted size: '{size}'")
        print(f"Extracted count: '{count}'")
        print(f"Quantity: {quantity}")

        session_id = req.get('session')

        # If the user orders Nuggets without specifying a count
        if food_item.lower() == 'nuggets' and not count:
            response_text = "How many pieces would you like for your nuggets? We have 8-count and 12-count."
            # Set output context with 'FoodItem' parameter
            output_contexts = [{
                "name": f"{session_id}/contexts/awaiting_nugget_count",
                "lifespanCount": 5,
                "parameters": {
                    "FoodItem": food_item,
                    "Size": size,
                    "number": quantity
                }
            }]
            return jsonify({
                'fulfillmentText': response_text,
                'outputContexts': output_contexts
            })

        # Concatenate size or count with food item if provided
        if count:
            full_item_name = f"{food_item} ({count})"
        elif size:
            full_item_name = f"{food_item} ({size})"
        else:
            full_item_name = food_item

        # Check if the item is in the price list
        if full_item_name not in price_list:
            response_text = f"Sorry, we don't have {full_item_name} on the menu."
            return jsonify({'fulfillmentText': response_text})

        # Add the item to the order
        order_item = {
            'food_item': full_item_name,
            'quantity': quantity
        }
        orders.setdefault(session_id, []).append(order_item)
        last_ordered_item[session_id] = order_item

        response_text = f"Great! I've added {quantity} {full_item_name} to your order. Would you like anything else?"
        return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'ProvideNuggetCount':
        # Handle providing the count for nuggets
        parameters = req.get('queryResult', {}).get('parameters', {})
        count = get_first(parameters.get('Count', '')).strip()
        quantity = get_first(parameters.get('number', 1))
        if quantity:
            quantity = int(quantity)
        else:
            quantity = 1

        # Retrieve 'FoodItem' from context
        contexts = req.get('queryResult', {}).get('outputContexts', [])
        food_item = ''
        for context in contexts:
            if 'awaiting_nugget_count' in context.get('name', ''):
                food_item = get_first(context.get(
                    'parameters', {}).get('FoodItem', '')).strip()
                break

        if not food_item:
            response_text = "Sorry, I'm not sure which item you're referring to. Please start your order again."
            return jsonify({'fulfillmentText': response_text})

        # Debugging statements
        print(f"Intent: {intent_name}")
        print(f"Parameters: {parameters}")
        print(f"Extracted food_item from context: '{food_item}'")
        print(f"Extracted count: '{count}'")
        print(f"Quantity: {quantity}")

        full_item_name = f"{food_item} ({count})"

        # Check if the item is in the price list
        if full_item_name not in price_list:
            response_text = f"Sorry, we don't have {full_item_name} on the menu."
            return jsonify({'fulfillmentText': response_text})

        session_id = req.get('session')

        # Add the item to the order
        order_item = {
            'food_item': full_item_name,
            'quantity': quantity
        }
        orders.setdefault(session_id, []).append(order_item)
        last_ordered_item[session_id] = order_item

        response_text = f"Great! I've added {quantity} {full_item_name} to your order. Would you like anything else?"
        return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'ModifyOrder':
        # Handle modifying an item in the order
        parameters = req.get('queryResult', {}).get('parameters', {})
        size = get_first(parameters.get('Size', '')).strip()
        count = get_first(parameters.get('Count', '')).strip()
        quantity = get_first(parameters.get('number', None))
        food_item = get_first(parameters.get('FoodItem', ''))
        if isinstance(food_item, str):
            food_item = food_item.strip()
        else:
            food_item = ''

        # Debugging statements
        print(f"Intent: {intent_name}")
        print(f"Parameters: {parameters}")
        print(f"Extracted food_item: '{food_item}'")
        print(f"Extracted size: '{size}'")
        print(f"Extracted count: '{count}'")
        print(f"Quantity: {quantity}")

        # If 'Count' is empty but 'Size' contains 'count', adjust accordingly
        if not count and 'count' in size.lower():
            count = size
            size = ''

        # Rest of your existing code...

        order_items = orders.get(session_id, [])
        if not order_items:
            response_text = "You don't have any items in your order to modify."
            return jsonify({'fulfillmentText': response_text})

        # Determine which item to modify
        if food_item:
            # Concatenate size or count with food item if provided
            if count:
                full_item_name = f"{food_item} ({count})"
            elif size:
                full_item_name = f"{food_item} ({size})"
            else:
                full_item_name = food_item
        else:
            # Modify the last ordered item if no food item specified
            last_item = last_ordered_item.get(session_id)
            if not last_item:
                response_text = "Please specify which item you'd like to modify."
                return jsonify({'fulfillmentText': response_text})
            full_item_name = last_item['food_item']
            # Update the food_item variable
            food_item = last_item['food_item']

        # Normalize item names for matching
        full_item_name_normalized = full_item_name.lower().strip()

        # Find the item in the order
        item_found = False
        for item in order_items:
            item_name_normalized = item['food_item'].lower().strip()
            if item_name_normalized == full_item_name_normalized or item_name_normalized.startswith(full_item_name_normalized.split('(')[0].strip()):
                # Modify the item
                if size or count:
                    # Update the size or count in the item name
                    parts = item['food_item'].split('(')
                    base_name = parts[0].strip()
                    if count:
                        new_item_name = f"{base_name} ({count})"
                    elif size:
                        new_item_name = f"{base_name} ({size})"
                    else:
                        new_item_name = base_name
                    item['food_item'] = new_item_name
                if quantity:
                    item['quantity'] = int(quantity)
                item_found = True
                # Update the last ordered item
                last_ordered_item[session_id] = item
                break

        if item_found:
            response_text = f"Your order has been updated."
        else:
            response_text = f"Could not find the item in your order to modify."

        return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'AddAnotherOne':
        # Handle adding another of the last ordered item
        last_item = last_ordered_item.get(session_id)
        if not last_item:
            response_text = "There is no recent item to add. What would you like to order?"
            return jsonify({'fulfillmentText': response_text})

        # Add another one of the last ordered item
        new_item = last_item.copy()
        orders[session_id].append(new_item)

        response_text = f"Added another {new_item['food_item']} to your order."
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
            # Generate order summary text
            order_summary = ''
            for item in order_items:
                quantity = item['quantity']
                food_item = item['food_item']
                order_summary += f"{quantity} x {food_item}\n"
            order_summary = order_summary.strip()

            # Calculate total price
            total_price = calculate_total(order_items)

            response_text = f"You have ordered:\n{order_summary}\nYour current total is ${total_price}. Would you like to confirm your order?"

        return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'ConfirmOrder':
        # Handle order confirmation
        response_text = "Your order has been placed successfully! Thank you for choosing Chick-fil-A."
        # Clear the order
        orders.pop(session_id, None)
        last_ordered_item.pop(session_id, None)
        return jsonify({'fulfillmentText': response_text})

    elif intent_name == 'CancelOrder':
        # Handle order cancellation
        orders.pop(session_id, None)
        last_ordered_item.pop(session_id, None)
        response_text = "Your order has been canceled. Let me know if you'd like to start a new order."
        return jsonify({'fulfillmentText': response_text})

    else:
        # Handle unrecognized intents
        response_text = "I'm sorry, I didn't understand that. Could you please rephrase?"
        return jsonify({'fulfillmentText': response_text})


@app.route('/')
def index():
    return render_template('index.html')

# If you're using the Dialogflow API directly for your frontend, ensure you have the necessary setup.
# The following code is optional and only required if you're making direct API calls from your frontend.


@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json.get('message')

    # Send the message to Dialogflow
    response = detect_intent_texts(
        'your-project-id', 'unique-session-id', [user_message], 'en-US')

    # Extract the reply
    bot_reply = response.query_result.fulfillment_text

    return jsonify({'reply': bot_reply})


def detect_intent_texts(project_id, session_id, texts, language_code):
    import dialogflow_v2 as dialogflow

    # Set the path to the service account key file if not set in environment variables
    # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/path/to/your/service-account-file.json'

    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)

    text_input = dialogflow.types.TextInput(
        text=texts[0], language_code=language_code)
    query_input = dialogflow.types.QueryInput(text=text_input)

    response = session_client.detect_intent(
        session=session, query_input=query_input)

    return response


if __name__ == "__main__":
    # Get the port from the environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
