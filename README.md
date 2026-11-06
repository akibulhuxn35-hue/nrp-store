# Online Sale — Flask E-commerce Starter

A mobile-responsive dark storefront built with Flask and SQLite.

## Run in Termux

```bash
pkg update -y && pkg upgrade -y
pkg install python -y
mkdir -p ~/online_sale
cd ~/online_sale
```

Copy/extract this project into `~/online_sale`, then:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="Use-A-Strong-Password-Here"
python app.py
```

Open `http://127.0.0.1:5000` in your phone browser. To access from another device on the same Wi-Fi, use the phone's LAN IP and port 5000.

## Admin
Use the email/password set in `ADMIN_EMAIL` and `ADMIN_PASSWORD`. If these variables are not set on the first run, the demo defaults are `admin@onlinesale.local` and `Admin@12345`. Change these before using the site for anything beyond local testing. The first initialization creates the admin user; changing environment variables later does not reset an existing admin password.

## Included
- Product catalogue, search and category filters
- Registration, login and logout
- Session-based shopping cart
- Checkout, order history and stock decrement
- Admin product creation/deletion and order status updates
- SQLite database automatically created as `online_sale.db`

## Important before public launch
This is a learning/demo starter, not a production-hardened store. Add CSRF protection, rate limiting, secure HTTPS cookies, email verification/password reset, image upload validation, backups, logging, and a real payment gateway. Set a long random `SECRET_KEY`; never publish the demo admin credentials. Use a production WSGI server and HTTPS rather than Flask's development server. Online card/UPI payment is not included.
