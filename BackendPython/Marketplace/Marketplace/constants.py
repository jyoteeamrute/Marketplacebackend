# constants.py

# Currency Choices
CURRENCY_CHOICES = [
    ("USD", "$"),
    ("INR", "₹"),
    ("EURO", "€"),
    ("GBP", "£"),
]

# Payment Modes
PAYMENT_MODES = [
    ("cash", "Cash"),
    ("card", "Card"),
    ("wallet", "Wallet"),
]

# Payment Status
PAYMENT_STATUS = [
    ("pending", "Pending"),
    ("succeeded", "Succeeded"),
    ("failed", "Failed"),
]

# Payment Direction
PAYMENT_DIRECTION = [
    ("credited", "Credited"),
    ("debited", "Debited"),
]

# Order Types
ORDER_TYPE_CHOICES = [
    ("Onsite", "onsite"),
    ("Click and Collect", "click_and_collect"),
    ("Delivery", "delivery"),
    ("onhome", "onhome"),
]
