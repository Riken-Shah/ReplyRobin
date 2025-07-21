"""
Tools for the reasoning agent using LangChain's tool decorator.
"""

from langchain_core.tools import tool
from typing import Dict, Any, List, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Mock data for tools
mock_subscription_data = {
    "user123": {
        "active_subscriptions": [
            {
                "id": "sub_123456",
                "product_id": "premium_monthly",
                "start_date": "2023-12-01",
                "renewal_date": "2024-01-01",
                "price": 9.99,
                "status": "active",
                "payment_method": "visa_4242",
            }
        ],
        "payment_history": [
            {
                "transaction_id": "tx_789012",
                "date": "2023-12-01",
                "amount": 9.99,
                "status": "completed",
                "description": "Premium Monthly Subscription",
            },
            {
                "transaction_id": "tx_789013",
                "date": "2023-12-01",
                "amount": 9.99,
                "status": "completed",
                "description": "Premium Monthly Subscription (duplicate)",
            },
        ],
        "available_products": [
            {
                "id": "premium_monthly",
                "name": "Premium Monthly",
                "price": 9.99,
                "billing_period": "monthly",
            },
            {
                "id": "premium_annual",
                "name": "Premium Annual",
                "price": 99.99,
                "billing_period": "annual",
            },
        ],
    }
}

mock_account_data = {
    "user123": {
        "user_id": "user123",
        "email": "user@example.com",
        "name": "John Doe",
        "created_at": "2023-01-15",
        "last_login": "2024-06-25",
        "account_type": "premium",
        "usage_stats": {
            "messages_sent": 1250,
            "responses_generated": 1200,
            "custom_characters": 3,
        },
        "preferences": {
            "email_notifications": True,
            "theme": "dark",
            "language": "en-US",
        },
    }
}

# FAQ data structure
faq_data = [
    {
        "question": "How do I cancel my subscription?",
        "answer": "To cancel your subscription, go to Settings > Subscription > Cancel Subscription. Your access will continue until the end of your current billing period.",
    },
    {
        "question": "How do I create a new character?",
        "answer": "To create a new character, go to the Characters tab and click on the '+' button. Follow the step-by-step wizard to customize your character's personality, knowledge, and appearance.",
    },
    {
        "question": "Why was I charged twice?",
        "answer": "Duplicate charges can sometimes occur due to payment processing issues. Please contact our support team with your transaction IDs, and we'll refund any duplicate charges within 3-5 business days.",
    },
    {
        "question": "How do I request an invoice?",
        "answer": "For invoice requests, please go to Settings > Billing > Request Invoice and fill out the form with your billing information. Invoices will be sent to your registered email address within 24 hours.",
    },
]

# Custom instructions memory
custom_instruction_memory = {}


@tool
def get_billing_information(user_id: str) -> Dict[str, Any]:
    """
    Fetches billing information for a user from RevenueCat (mock).

    Args:
        user_id: The unique identifier for the user

    Returns:
        Dictionary containing the user's subscription information, payment history, and available products
    """
    logging.info(f"Fetching billing information for user: {user_id}")

    if user_id in mock_subscription_data:
        return mock_subscription_data[user_id]
    else:
        return {"error": "User not found", "status": 404}


@tool
def get_account_information(user_id: str) -> Dict[str, Any]:
    """
    Fetches account information for a user.

    Args:
        user_id: The unique identifier for the user

    Returns:
        Dictionary containing the user's account details, including email, name, account type, and usage stats
    """
    logging.info(f"Fetching account information for user: {user_id}")

    if user_id in mock_account_data:
        return mock_account_data[user_id]
    else:
        return {"error": "User not found", "status": 404}


@tool
def search_faqs(query: str) -> List[Dict[str, str]]:
    """
    Searches through FAQs based on a query.

    Args:
        query: The search query to match against FAQ questions

    Returns:
        List of matching FAQ entries (question and answer pairs)
    """
    logging.info(f"Searching FAQs for query: {query}")

    # Simple search implementation - in production use a proper search algorithm
    query = query.lower()
    results = []

    for faq in faq_data:
        if query in faq["question"].lower() or query in faq["answer"].lower():
            results.append(faq)

    return results


@tool
def store_custom_instruction(
    user_id: str, instruction_key: str, instruction_value: str
) -> Dict[str, Any]:
    """
    Stores a custom instruction for a user.

    Args:
        user_id: The unique identifier for the user
        instruction_key: The key/name of the instruction
        instruction_value: The content of the instruction

    Returns:
        Dictionary containing the status of the operation
    """
    logging.info(
        f"Storing custom instruction for user: {user_id}, key: {instruction_key}"
    )

    if user_id not in custom_instruction_memory:
        custom_instruction_memory[user_id] = {}

    custom_instruction_memory[user_id][instruction_key] = instruction_value

    return {
        "status": "success",
        "message": f"Custom instruction '{instruction_key}' stored successfully",
    }


@tool
def get_custom_instruction(user_id: str, instruction_key: str = None) -> Dict[str, Any]:
    """
    Retrieves custom instructions for a user.

    Args:
        user_id: The unique identifier for the user
        instruction_key: Optional key to get a specific instruction

    Returns:
        Dictionary containing the requested instructions or all instructions if no key provided
    """
    logging.info(f"Getting custom instruction(s) for user: {user_id}")

    if user_id not in custom_instruction_memory:
        return {"error": "No instructions found for user", "status": 404}

    if instruction_key:
        if instruction_key in custom_instruction_memory[user_id]:
            return {
                "instruction": {
                    instruction_key: custom_instruction_memory[user_id][instruction_key]
                }
            }
        else:
            return {
                "error": f"Instruction '{instruction_key}' not found",
                "status": 404,
            }
    else:
        return {"instructions": custom_instruction_memory[user_id]}


# Export all tools in a list for easy import
available_tools = [
    get_billing_information,
    get_account_information,
    search_faqs,
    store_custom_instruction,
    get_custom_instruction,
]
