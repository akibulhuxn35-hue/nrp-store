import os, sqlite3, secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
app.config["DATABASE"] = os.path.join(app.root_path, "online_sale.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      is_admin INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS products (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '', price REAL NOT NULL,
      category TEXT NOT NULL DEFAULT 'General', image TEXT NOT NULL DEFAULT '',
      stock INTEGER NOT NULL DEFAULT 10, featured INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      customer_name TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL,
      total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS order_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL, product_name TEXT NOT NULL,
      price REAL NOT NULL, quantity INTEGER NOT NULL,
      FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    """)
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        samples = [
          ("Aurora Headphones","Immersive sound, soft cushions and long battery life.",2499,"Electronics","https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=900",18,1),
          ("Minimal Watch","A clean everyday timepiece with a premium finish.",3199,"Fashion","https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=900",12,1),
          ("Urban Backpack","A versatile backpack for work, travel and daily use.",1899,"Accessories","https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=900",20,1),
          ("Studio Speaker","Compact wireless speaker with rich, balanced audio.",2799,"Electronics","https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=900",9,0),
          ("Classic Sneakers","Comfortable streetwear sneakers for everyday style.",2299,"Fashion","https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=900",15,0),
          ("Desk Lamp","Modern ambient lighting for a focused workspace.",1499,"Home","https://images.unsplash.com/photo-150 પ્રકાશ?w=900",7,0)
        ]
        # Replace any malformed sample image with a valid remote image.
        samples[-1] = ("Desk Lamp","Modern ambient lighting for a focused workspace.",1499,"Home","https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=900",7,0)
        conn.executemany("INSERT INTO products(name,description,price,category,image,stock,featured) VALUES(?,?,?,?,?,?,?)", samples)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@onlinesale.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    existing = conn.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
    if not existing:
        conn.execute("INSERT INTO users(name,email,password,is_admin) VALUES(?,?,?,1)",
                     ("Store Admin", admin_email, generate_password_hash(admin_password)))
    conn.commit()
    conn.close()

@app.context_processor
def common():
    cart = session.get("cart", {})
    return {"cart_count": sum(int(q) for q in cart.values()),
            "current_user": session.get("user")}

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user") or not session["user"].get("is_admin"):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql, params = "SELECT * FROM products WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category=?"
        params.append(category)
    sql += " ORDER BY featured DESC, id DESC"
    products = db().execute(sql, params).fetchall()
    categories = db().execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return render_template("index.html", products=products, categories=categories, q=q, category=category)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db().execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product: abort(404)
    return render_template("product.html", product=product)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email = request.form.get("name","").strip(), request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "danger")
        else:
            try:
                db().execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                             (name,email,generate_password_hash(password)))
                db().commit()
                flash("Account created. Please sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "danger")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form.get("password","")):
            session.clear()
            session["user"] = {"id":user["id"],"name":user["name"],"email":user["email"],"is_admin":bool(user["is_admin"])}
            flash("Welcome back!", "success")
            return redirect(url_for("admin") if user["is_admin"] else url_for("index"))
        flash("Incorrect email or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    items, total = [], 0
    for pid, qty in session.get("cart", {}).items():
        p = db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            subtotal = p["price"] * int(qty)
            items.append({"product":p,"quantity":int(qty),"subtotal":subtotal})
            total += subtotal
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    p = db().execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not p: abort(404)
    cart = session.get("cart", {})
    cart[str(product_id)] = min(int(cart.get(str(product_id),0))+1, p["stock"])
    session["cart"] = cart
    flash("Added to your cart.", "success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart/update", methods=["POST"])
def update_cart():
    cart = session.get("cart", {})
    for pid in list(cart):
        try:
            qty = int(request.form.get(pid, 0))
        except ValueError:
            qty = 0
        p = db().execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
        if not p or qty <= 0: cart.pop(pid, None)
        else: cart[pid] = min(qty, p["stock"])
    session["cart"] = cart
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET","POST"])
@login_required
def checkout():
    cart = session.get("cart", {})
    products, total = [], 0
    for pid, qty in cart.items():
        p = db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            products.append((p,int(qty)))
            total += p["price"]*int(qty)
    if not products:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("index"))
    if request.method == "POST":
        name, phone, address = (request.form.get(k,"").strip() for k in ("name","phone","address"))
        if not name or not phone or not address:
            flash("Please complete all delivery details.", "danger")
        elif any(qty > p["stock"] for p,qty in products):
            flash("A product quantity is no longer available. Please update your cart.", "danger")
        else:
            conn = db()
            cur = conn.execute("INSERT INTO orders(user_id,customer_name,phone,address,total) VALUES(?,?,?,?,?)",
                               (session["user"]["id"],name,phone,address,total))
            oid = cur.lastrowid
            for p,qty in products:
                conn.execute("INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?,?,?)",
                             (oid,p["id"],p["name"],p["price"],qty))
                conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty,p["id"]))
            conn.commit()
            session["cart"] = {}
            flash(f"Order #{oid} placed successfully. Payment is currently cash on delivery / manual.", "success")
            return redirect(url_for("my_orders"))
    return render_template("checkout.html", products=products, total=total)

@app.route("/orders")
@login_required
def my_orders():
    orders = db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",
                          (session["user"]["id"],)).fetchall()
    return render_template("orders.html", orders=orders)

@app.route("/admin")
@admin_required
def admin():
    products = db().execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    orders = db().execute("SELECT orders.*, users.email FROM orders JOIN users ON users.id=orders.user_id ORDER BY orders.id DESC").fetchall()
    stats = {"products":len(products), "orders":len(orders),
             "sales":db().execute("SELECT COALESCE(SUM(total),0) FROM orders").fetchone()[0]}
    return render_template("admin.html", products=products, orders=orders, stats=stats)

@app.route("/admin/product", methods=["POST"])
@admin_required
def admin_add_product():
    name = request.form.get("name","").strip()
    try:
        price, stock = float(request.form.get("price",0)), int(request.form.get("stock",0))
    except ValueError:
        flash("Price and stock must be numbers.", "danger")
        return redirect(url_for("admin"))
    if not name or price < 0 or stock < 0:
        flash("Please enter valid product details.", "danger")
    else:
        db().execute("INSERT INTO products(name,description,price,category,image,stock,featured) VALUES(?,?,?,?,?,?,?)",
          (name,request.form.get("description",""),price,request.form.get("category","General"),
           request.form.get("image",""),stock,1 if request.form.get("featured") else 0))
        db().commit()
        flash("Product added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_delete_product(pid):
    db().execute("DELETE FROM products WHERE id=?", (pid,))
    db().commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/order/<int:oid>", methods=["POST"])
@admin_required
def admin_order_status(oid):
    status = request.form.get("status","Pending")
    if status not in ("Pending","Processing","Shipped","Delivered","Cancelled"): abort(400)
    db().execute("UPDATE orders SET status=? WHERE id=?", (status,oid))
    db().commit()
    flash("Order status updated.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(403)
def forbidden(e): return render_template("error.html", code=403, message="You don't have permission to view this page."),403
@app.errorhandler(404)
def not_found(e): return render_template("error.html", code=404, message="The page you're looking for does not exist."),404

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
