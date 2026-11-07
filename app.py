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
    conn.execute("""
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        pincode TEXT NOT NULL,
        house TEXT NOT NULL,
        area TEXT NOT NULL,
        landmark TEXT DEFAULT '',
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        address_type TEXT NOT NULL DEFAULT 'Home',
        is_default INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN owner_id INTEGER")

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
    admin_row = conn.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
    if admin_row:
        conn.execute("UPDATE products SET owner_id=? WHERE owner_id IS NULL", (admin_row[0],))

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

@app.route("/addresses", methods=["GET", "POST"])
@login_required
def addresses():
    uid = session["user"]["id"]
    conn = db()

    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        pincode = request.form.get("pincode", "").strip()
        house = request.form.get("house", "").strip()
        area = request.form.get("area", "").strip()
        landmark = request.form.get("landmark", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        address_type = request.form.get("address_type", "Home")
        if (not all([name, phone, pincode, house, area, city, state])
                or not phone.isdigit() or len(phone) != 10
                or not pincode.isdigit() or len(pincode) != 6
                or address_type not in ("Home", "Work")):
            flash("Please enter valid delivery details.", "danger")
        else:
            is_default = 1 if not conn.execute(
                "SELECT id FROM addresses WHERE user_id=?", (uid,)
            ).fetchone() else 0
            conn.execute(
                """INSERT INTO addresses
                (user_id,full_name,phone,pincode,house,area,landmark,city,state,address_type,is_default)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (uid,name,phone,pincode,house,area,landmark,city,state,address_type,is_default)
            )
            conn.commit()
            flash("Delivery address saved.", "success")
            return redirect(url_for("addresses"))

    saved = conn.execute(
        "SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC",
        (uid,)
    ).fetchall()
    return render_template("addresses.html", addresses=saved)



@app.route("/addresses/<int:address_id>/edit", methods=["GET", "POST"])
@login_required
def edit_address(address_id):
    uid = session["user"]["id"]
    conn = db()
    address = conn.execute(
        "SELECT * FROM addresses WHERE id=? AND user_id=?",
        (address_id, uid)
    ).fetchone()
    if not address:
        abort(404)

    if request.method == "POST":
        fields = {
            key: request.form.get(key, "").strip()
            for key in ("full_name", "phone", "pincode", "house",
                        "area", "landmark", "city", "state")
        }
        address_type = request.form.get("address_type", "Home")
        if (not all(fields[k] for k in
                    ("full_name", "phone", "pincode", "house",
                     "area", "city", "state"))
                or not fields["phone"].isdigit()
                or len(fields["phone"]) != 10
                or not fields["pincode"].isdigit()
                or len(fields["pincode"]) != 6
                or address_type not in ("Home", "Work")):
            flash("Please enter valid delivery details.", "danger")
        else:
            conn.execute("""
                UPDATE addresses SET full_name=?, phone=?, pincode=?,
                house=?, area=?, landmark=?, city=?, state=?, address_type=?
                WHERE id=? AND user_id=?
            """, (*fields.values(), address_type, address_id, uid))
            conn.commit()
            flash("Address updated.", "success")
            return redirect(url_for("addresses"))

    return render_template("edit_address.html", address=address)


@app.route("/addresses/<int:address_id>/delete", methods=["POST"])
@login_required
def delete_address(address_id):
    uid = session["user"]["id"]
    conn = db()
    conn.execute(
        "DELETE FROM addresses WHERE id=? AND user_id=?",
        (address_id, uid)
    )
    conn.commit()
    flash("Address deleted if it existed.", "success")
    return redirect(url_for("addresses"))


@app.route("/addresses/<int:address_id>/default", methods=["POST"])
@login_required
def default_address(address_id):
    uid = session["user"]["id"]
    conn = db()
    address = conn.execute(
        "SELECT id FROM addresses WHERE id=? AND user_id=?",
        (address_id, uid)
    ).fetchone()
    if not address:
        abort(404)

    conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (uid,))
    conn.execute(
        "UPDATE addresses SET is_default=1 WHERE id=? AND user_id=?",
        (address_id, uid)
    )
    conn.commit()
    flash("Default address updated.", "success")
    return redirect(url_for("addresses"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    uid = session["user"]["id"]
    conn = db()
    cart = session.get("cart", {})
    products, total = [], 0

    for pid, qty in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            products.append((p, int(qty)))
            total += p["price"] * int(qty)

    if not products:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        choice = request.form.get("delivery_choice", "new")
        name = phone = address = ""

        if choice != "new":
            saved = conn.execute(
                "SELECT * FROM addresses WHERE id=? AND user_id=?",
                (choice, uid)
            ).fetchone()

            if saved:
                name = saved["full_name"]
                phone = saved["phone"]
                address = (
                    f'{saved["house"]}, {saved["area"]}, {saved["landmark"]}\n'
                    f'{saved["city"]}, {saved["state"]} - {saved["pincode"]}'
                )
            else:
                flash("Please select a valid saved address.", "danger")

        else:
            name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip()
            pincode = request.form.get("pincode", "").strip()
            house = request.form.get("house", "").strip()
            area = request.form.get("area", "").strip()
            landmark = request.form.get("landmark", "").strip()
            city = request.form.get("city", "").strip()
            state = request.form.get("state", "").strip()
            address_type = request.form.get("address_type", "Home")

            if (not all([name, phone, pincode, house, area, city, state])
                    or not phone.isdigit() or len(phone) != 10
                    or not pincode.isdigit() or len(pincode) != 6
                    or address_type not in ("Home", "Work")):
                flash("Please enter valid delivery details.", "danger")
            else:
                address = (
                    f"{house}, {area}, {landmark}\n"
                    f"{city}, {state} - {pincode}"
                )

        if not name or not phone or not address:
            if not any("valid" in str(x) for x in []):
                pass
        elif any(qty > p["stock"] for p, qty in products):
            flash("A product quantity is no longer available. Please update your cart.", "danger")
        else:
            if choice == "new" and request.form.get("save_address") == "yes":
                is_default = 1 if not conn.execute(
                    "SELECT id FROM addresses WHERE user_id=?", (uid,)
                ).fetchone() else 0
                conn.execute(
                    """INSERT INTO addresses
                    (user_id,full_name,phone,pincode,house,area,landmark,city,state,address_type,is_default)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (uid,name,phone,pincode,house,area,landmark,city,state,address_type,is_default)
                )

            cur = conn.execute(
                "INSERT INTO orders(user_id,customer_name,phone,address,total) VALUES(?,?,?,?,?)",
                (uid,name,phone,address,total)
            )
            oid = cur.lastrowid

            for product, qty in products:
                conn.execute(
                    "INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?,?,?)",
                    (oid,product["id"],product["name"],product["price"],qty)
                )
                conn.execute(
                    "UPDATE products SET stock=stock-? WHERE id=?",
                    (qty,product["id"])
                )

            conn.commit()
            session["cart"] = {}
            flash(f"Order #{oid} placed successfully. Payment is currently cash on delivery / manual.", "success")
            return redirect(url_for("my_orders"))

    saved_addresses = conn.execute(
        "SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC",
        (uid,)
    ).fetchall()

    return render_template(
        "checkout.html",
        products=products,
        total=total,
        addresses=saved_addresses
    )

@app.route("/orders")
@login_required
def my_orders():
    orders = db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",
                          (session["user"]["id"],)).fetchall()
    return render_template("orders.html", orders=orders)

@app.route("/admin")
@admin_required
def admin():
    products = db().execute("SELECT * FROM products WHERE owner_id=? ORDER BY id DESC", (session["user"]["id"],)).fetchall()
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
        db().execute("INSERT INTO products(name,description,price,category,image,stock,featured,owner_id) VALUES(?,?,?,?,?,?,?,?)",
          (name,request.form.get("description",""),price,request.form.get("category","General"),
           request.form.get("image",""),stock,1 if request.form.get("featured") else 0,session["user"]["id"]))
        db().commit()
        flash("Product added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:pid>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_product(pid):
    product = db().execute(
        "SELECT * FROM products WHERE id=? AND owner_id=?",
        (pid, session["user"]["id"])
    ).fetchone()

    if product is None:
        abort(404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        try:
            price = float(request.form.get("price", 0))
            stock = int(request.form.get("stock", 0))
        except ValueError:
            flash("Price and stock must be numbers.", "danger")
            return render_template("edit_product.html", product=product)

        if not name or price < 0 or stock < 0:
            flash("Please enter valid product details.", "danger")
            return render_template("edit_product.html", product=product)

        db().execute(
            """UPDATE products SET name=?, description=?, price=?, category=?,
               image=?, stock=?, featured=?
               WHERE id=? AND owner_id=?""",
            (name, request.form.get("description", ""), price,
             request.form.get("category", "General"), request.form.get("image", ""),
             stock, 1 if request.form.get("featured") else 0,
             pid, session["user"]["id"])
        )
        db().commit()
        flash("Your product has been updated.", "success")
        return redirect(url_for("admin"))

    return render_template("edit_product.html", product=product)


@app.route("/admin/product/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_delete_product(pid):
    result = db().execute(
        "DELETE FROM products WHERE id=? AND owner_id=?",
        (pid, session["user"]["id"])
    )
    if result.rowcount == 0:
        abort(404)
    db().commit()
    flash("Your product has been deleted.", "success")
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
