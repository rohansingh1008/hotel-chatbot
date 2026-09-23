import os
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

client = Client()
DATASET_NAME = "hotel-chatbot-eval"

examples = [
    {
        "inputs": {"question": "What time is check-in?"},
        "outputs": {"expected_tool": "get_hotel_info", "expected_args": {"topic": "check_in_time"}},
    },
    {
        "inputs": {"question": "Does the hotel have a swimming pool?"},
        "outputs": {"expected_tool": "get_hotel_info", "expected_args": {"topic": "pool"}},
    },
    {
        "inputs": {"question": "Is breakfast included?"},
        "outputs": {"expected_tool": "get_hotel_info", "expected_args": {"topic": "breakfast"}},
    },
    {
        "inputs": {"question": "What is the cancellation policy?"},
        "outputs": {"expected_tool": "get_hotel_info", "expected_args": {"topic": "cancellation_policy"}},
    },
    {
        "inputs": {"question": "Which room is suitable for three guests at Sunrise Grand Hotel?"},
        "outputs": {
            "expected_tool": "find_room_by_capacity",
            "expected_args": {"hotel_name": "Sunrise", "guests": 3},
        },
    },
    {
        "inputs": {"question": "Do you have double rooms available at Blue Horizon Inn from 2026-11-01 to 2026-11-03?"},
        "outputs": {
            "expected_tool": "check_room_availability",
            "expected_args": {
                "hotel_name": "Blue Horizon",
                "room_type": "double",
                "check_in": "2026-11-01",
                "check_out": "2026-11-03",
            },
        },
    },
]

if not client.has_dataset(dataset_name=DATASET_NAME):
    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="Hotel chatbot correctness + quality eval set",
    )
    for ex in examples:
        client.create_example(inputs=ex["inputs"], outputs=ex["outputs"], dataset_id=dataset.id)
    print(f"Created dataset '{DATASET_NAME}' with {len(examples)} examples.")
else:
    print(f"Dataset '{DATASET_NAME}' already exists — skipping.")