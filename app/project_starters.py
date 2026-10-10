PROJECT_STARTERS = [
    {
        "slug": "hello-python", "title": "Hello, Python!", "level": "Beginner",
        "description": "Print a greeting and use a variable to personalize it.",
        "code": '''name = "Python learner"
print(f"Hello, {name}!")
print("Your project is ready to grow.")''',
    },
    {
        "slug": "age-next-year", "title": "Age next year", "level": "Beginner",
        "description": "Store a number and calculate what it will be next year.",
        "code": '''age = 16
next_year = age + 1
print(f"You are {age} years old.")
print(f"Next year, you will be {next_year}.")''',
    },
    {
        "slug": "tip-calculator", "title": "Tip calculator", "level": "Beginner",
        "description": "Calculate a tip and split the bill between friends.",
        "code": '''bill = 1250.00
tip_percent = 10
people = 4

tip = bill * tip_percent / 100
total = bill + tip
per_person = total / people

print(f"Tip: Rs. {tip:.2f}")
print(f"Total: Rs. {total:.2f}")
print(f"Each person pays: Rs. {per_person:.2f}")''',
    },
    {
        "slug": "temperature-converter", "title": "Temperature converter", "level": "Beginner",
        "description": "Convert Celsius temperatures to Fahrenheit with a function.",
        "code": '''def to_fahrenheit(celsius):
    return celsius * 9 / 5 + 32

for celsius in [0, 20, 37, 100]:
    print(f"{celsius}°C = {to_fahrenheit(celsius):.1f}°F")''',
    },
    {
        "slug": "times-table", "title": "Multiplication table", "level": "Beginner",
        "description": "Use a loop to print a neat multiplication table.",
        "code": '''number = 7

for multiplier in range(1, 11):
    answer = number * multiplier
    print(f"{number:>2} × {multiplier:>2} = {answer:>2}")''',
    },
    {
        "slug": "word-counter", "title": "Word counter", "level": "Beginner",
        "description": "Count words, characters, and sentences in a sample paragraph.",
        "code": '''text = "Python makes it fun to build useful projects. Keep practicing!"
words = text.split()
sentences = [part for part in text.split("!") if part.strip()]

print(f"Words: {len(words)}")
print(f"Characters: {len(text)}")
print(f"Sentences: {len(sentences)}")''',
    },
    {
        "slug": "todo-checklist", "title": "To-do checklist", "level": "Basic",
        "description": "Track tasks in a list and mark completed work.",
        "code": '''tasks = [
    {"name": "Learn variables", "done": True},
    {"name": "Practice loops", "done": False},
    {"name": "Build a project", "done": False},
]

for task in tasks:
    mark = "✓" if task["done"] else "○"
    print(f"{mark} {task['name']}")

complete = sum(task["done"] for task in tasks)
print(f"Progress: {complete}/{len(tasks)} tasks")''',
    },
    {
        "slug": "contact-book", "title": "Contact book", "level": "Basic",
        "description": "Store contacts in a dictionary and search for a person.",
        "code": '''contacts = {
    "Asha": "9800000001",
    "Nima": "9800000002",
    "Sam": "9800000003",
}

name_to_find = "Nima"
phone = contacts.get(name_to_find)

if phone:
    print(f"{name_to_find}: {phone}")
else:
    print(f"{name_to_find} is not in your contacts.")

print(f"Saved contacts: {len(contacts)}")''',
    },
    {
        "slug": "quiz-score-tracker", "title": "Quiz score tracker", "level": "Basic",
        "description": "Calculate a learner's score and give a friendly result.",
        "code": '''answers = [True, True, False, True, False]
correct = sum(answers)
total = len(answers)
percentage = correct / total * 100

print(f"Score: {correct}/{total}")
print(f"Accuracy: {percentage:.0f}%")

if percentage >= 80:
    print("Great work — you have this topic!")
elif percentage >= 60:
    print("Good start — review a couple of ideas.")
else:
    print("Keep practicing. Every attempt helps!")''',
    },
    {
        "slug": "number-guessing", "title": "Number guessing game", "level": "Basic",
        "description": "Practice conditions and attempts using a repeatable game example.",
        "code": '''secret = 23
guesses = [10, 30, 23]

for attempt, guess in enumerate(guesses, start=1):
    print(f"Attempt {attempt}: {guess}")
    if guess < secret:
        print("Too low!")
    elif guess > secret:
        print("Too high!")
    else:
        print("Correct — you guessed it!")
        break''',
    },
    {
        "slug": "rock-paper-scissors", "title": "Rock, paper, scissors", "level": "Basic",
        "description": "Compare two choices and decide the winner with conditions.",
        "code": '''rounds = [("rock", "scissors"), ("paper", "rock"), ("scissors", "scissors")]

for player, computer in rounds:
    if player == computer:
        result = "Tie"
    elif (player, computer) in [("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")]:
        result = "Player wins"
    else:
        result = "Computer wins"
    print(f"Player: {player} | Computer: {computer} → {result}")''',
    },
    {
        "slug": "expense-tracker", "title": "Expense tracker", "level": "Intermediate",
        "description": "Group expenses by category and find the biggest cost.",
        "code": '''expenses = [
    ("Food", 450), ("Travel", 300), ("Food", 250),
    ("Books", 800), ("Travel", 150),
]
totals = {}

for category, amount in expenses:
    totals[category] = totals.get(category, 0) + amount

for category, amount in sorted(totals.items()):
    print(f"{category:8} Rs. {amount:>5}")

print(f"Total spent: Rs. {sum(totals.values())}")''',
    },
    {
        "slug": "fibonacci", "title": "Fibonacci sequence", "level": "Intermediate",
        "description": "Generate a sequence by adding the previous two values.",
        "code": '''def fibonacci(count):
    sequence = []
    first, second = 0, 1
    for _ in range(count):
        sequence.append(first)
        first, second = second, first + second
    return sequence

print(fibonacci(12))''',
    },
    {
        "slug": "prime-checker", "title": "Prime number checker", "level": "Intermediate",
        "description": "Write a function that checks whether a number is prime.",
        "code": '''def is_prime(number):
    if number < 2:
        return False
    for divisor in range(2, int(number ** 0.5) + 1):
        if number % divisor == 0:
            return False
    return True

for value in [1, 2, 9, 17, 25, 29]:
    print(f"{value}: {'prime' if is_prime(value) else 'not prime'}")''',
    },
    {
        "slug": "palindrome-checker", "title": "Palindrome checker", "level": "Intermediate",
        "description": "Normalize text and check whether it reads the same backwards.",
        "code": '''def is_palindrome(text):
    cleaned = "".join(char.lower() for char in text if char.isalnum())
    return cleaned == cleaned[::-1]

examples = ["level", "Python", "Never odd or even"]
for phrase in examples:
    result = "yes" if is_palindrome(phrase) else "no"
    print(f"{phrase!r}: palindrome? {result}")''',
    },
    {
        "slug": "unit-converter", "title": "Unit converter", "level": "Intermediate",
        "description": "Convert distances between kilometres, miles, metres, and feet.",
        "code": '''def convert_km(kilometres):
    return {
        "miles": kilometres * 0.621371,
        "metres": kilometres * 1000,
        "feet": kilometres * 3280.84,
    }

distance = 5
for unit, value in convert_km(distance).items():
    print(f"{distance} km = {value:.2f} {unit}")''',
    },
    {
        "slug": "bank-account", "title": "Bank account class", "level": "Advanced",
        "description": "Model account data and safe deposits and withdrawals with a class.",
        "code": '''class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        if amount > 0:
            self.balance += amount

    def withdraw(self, amount):
        if 0 < amount <= self.balance:
            self.balance -= amount
            return True
        return False

account = BankAccount("Prakriti", 1200)
account.deposit(500)
account.withdraw(300)
print(f"{account.owner}'s balance: Rs. {account.balance}")''',
    },
    {
        "slug": "book-library", "title": "Book library", "level": "Advanced",
        "description": "Use classes and list filtering to manage a tiny library.",
        "code": '''class Book:
    def __init__(self, title, author, available=True):
        self.title = title
        self.author = author
        self.available = available

books = [
    Book("Python Basics", "A. Rai"),
    Book("Data Stories", "B. Lama", False),
    Book("Tiny Algorithms", "C. Shah"),
]

for book in books:
    status = "available" if book.available else "checked out"
    print(f"{book.title} — {book.author} ({status})")

print("Available:", sum(book.available for book in books))''',
    },
    {
        "slug": "csv-grade-report", "title": "CSV grade report", "level": "Advanced",
        "description": "Read CSV data from memory and calculate a class average.",
        "code": '''import csv
from io import StringIO

data = "name,score\\nAsha,88\\nNima,94\\nSam,76\\n"
rows = csv.DictReader(StringIO(data))
students = [(row["name"], int(row["score"])) for row in rows]

for name, score in students:
    print(f"{name:8} {score}%")

average = sum(score for _, score in students) / len(students)
print(f"Class average: {average:.1f}%")''',
    },
    {
        "slug": "file-extension-organizer", "title": "File extension organizer", "level": "Advanced",
        "description": "Group example file names by extension without changing your files.",
        "code": '''from pathlib import PurePath

file_names = [
    "notes.txt", "photo.png", "report.pdf", "logo.png",
    "script.py", "data.csv", "readme.txt",
]
groups = {}

for file_name in file_names:
    extension = PurePath(file_name).suffix.lower() or "(no extension)"
    groups.setdefault(extension, []).append(file_name)

for extension, names in sorted(groups.items()):
    print(f"{extension}: {', '.join(names)}")''',
    },
]
