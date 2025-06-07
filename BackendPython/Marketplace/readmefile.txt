
to run project with `python manage.py runserver` and then access it at `http://127.0.0.1:8000'

go inside project directory --
/MARKETPLACE/Marketplace-082024-001/BackendPython/Marketplace
├── Admin               # Admin panel and user management (Superuser access)
├── ProfessionalUser    # Standard user accounts (Company users)
├── UserApp            # Regular customer accounts (End-users)
├── manage.py          # Django project management script
├── requirements.txt   # Python dependencies list
├── readmefile.txt     # Documentation (this file)
└── Marketplace        # Django project directory



python -m venv env or python3 -m venv myenv
source env/bin/activate or source myenv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations if not created migration files(optional)
python manage.py migrate
python manage.py runserver

http://127.0.0.1:8000/

using seperate jwt auth for professionals and users

Marketplace Backend Setup Guide for development process 

1️⃣ Setting Up the Virtual Environment
# Create a virtual environment
python -m venv env  # or python3 -m venv env

# Activate the virtual environment
source env/bin/activate  # For Linux/macOS
env\Scripts\activate  # For Windows (PowerShell)

# Install required dependencies
pip install -r requirements.txt


2️⃣ Database Configuration (MySQL)-----ignore it if you are using sqlite default db

Creating the Database

CREATE DATABASE marketplacedb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

By default, MySQL may use latin1 encoding, which does not fully support Unicode characters. To ensure full Unicode support:

Creating a MySQL User---
CREATE USER 'marketplaceuser'@'localhost' IDENTIFIED BY 'marketplace@2025!';
GRANT ALL PRIVILEGES ON marketplacedb.* TO 'marketplaceuser'@'localhost';
FLUSH PRIVILEGES;

✅ If Django is running on a remote server, use 'marketplaceuser'@'%' to allow remote connections.
✅ For read-only access, grant SELECT privileges instead of ALL PRIVILEGES.
✅ To remove the user, use: DROP USER 'marketplaceuser'@'localhost';
Configuring Django to Use MySQL
settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'marketplace_db',
        'USER': 'marketplaceuser',
        'PASSWORD': 'marketplace@2025!',
        'HOST': 'localhost',  # Change if using a remote MySQL server
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

3️⃣ Configuring Django to Use MySQL------------------
python manage.py makemigrations  # If migration files are not created (optional)
python manage.py migrate  # Apply database migrations
python manage.py runserver  # Start the Django development server


5️⃣ Project Structure Overview for Now if any updation required manation here 

/MARKETPLACE/Marketplace-082024-001/BackendPython/Marketplace
├── Admin               # Admin panel and user management (Superuser access)
├── ProfessionalUser    # Standard user accounts (Company users)
├── UserApp            # Regular customer accounts (End-users)
├── manage.py          # Django project management script
├── requirements.txt   # Python dependencies list
├── readmefile.txt     # Documentation (this file)
└── Marketplace        # Django project directory



6️⃣ User Roles Overview(Add more roles as needed) exact what we need

Admin: Manages all users, roles, and system configurations. mean Fully access of project web and app

Professional User: Business users with extended functionality.

Customer User: Regular users accessing marketplace features.


Note------
✔ Use .env for sensitive keys instead of settings.py.
dont't push your env on git
Always use try accept in your code add comment for your code
 

alway use need and clean your code and migrations 