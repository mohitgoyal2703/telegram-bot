from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import logging
import json
import os
from datetime import datetime

# 🔇 reduce error spam
logging.basicConfig(level=logging.ERROR)


TOKEN = os.getenv("BOT_TOKEN")

# 👑 ADMINS
MAIN_ADMINS = [1232325263]
VIEW_ADMINS = [791363068]
ALL_ADMINS = MAIN_ADMINS + VIEW_ADMINS

# FILES
PRODUCTS_FILE = "products.json"
ORDER_HISTORY_FILE = "order_history.json"
USERS_FILE = "users.json"

# DEFAULT PRODUCTS
DEFAULT_PRODUCTS = {
    "p1": {"name": "Myntra ₹100 Off", "price": 30, "file": "myntra100.txt"},
    "p2": {"name": "Myntra ₹150 Off", "price": 25, "file": "myntra150.txt"},
}

# PAYMENT
LOW_UPI = "Q703671699@ybl"
HIGH_UPI = "mohitgoy1al21-1@okhdfcbank"

LOW_QR = "qr.png"
HIGH_QR = "qr2.png"


# ---------------- FILE HELPERS ----------------
def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if not os.path.exists(PRODUCTS_FILE):
    save_json(PRODUCTS_FILE, DEFAULT_PRODUCTS)

products = load_json(PRODUCTS_FILE, DEFAULT_PRODUCTS)


# ---------------- SAFE ANSWER ----------------
async def safe_answer(query, text=None, show_alert=False):
    try:
        await query.answer(text=text, show_alert=show_alert)
    except:
        pass


# ---------------- STOCK ----------------
def get_stock(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return len([line for line in f if line.strip()])
    except:
        return 0


# ---------------- GET CODES ----------------
def get_codes(filename, qty):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except:
        return None

    if len(lines) < qty:
        return None

    selected = lines[:qty]
    remaining = lines[qty:]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(remaining) + ("\n" if remaining else ""))

    return selected


# ---------------- ORDER HISTORY ----------------
def load_order_history():
    return load_json(ORDER_HISTORY_FILE, [])


def save_order_history(history):
    save_json(ORDER_HISTORY_FILE, history)


def save_user(user):
    users = load_json(USERS_FILE, [])
    if user.id not in users:
        users.append(user.id)
        save_json(USERS_FILE, users)


def add_order_history(entry):
    history = load_order_history()
    history.append(entry)
    save_order_history(history)


def update_order_status(user_id, product_id, qty, new_status):
    history = load_order_history()
    for item in reversed(history):
        if (
            item.get("user_id") == user_id
            and item.get("product_id") == product_id
            and item.get("qty") == qty
            and item.get("status") in ["payment_sent", "pending"]
        ):
            item["status"] = new_status
            item["updated_at"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            save_order_history(history)
            return item
    return None


# ---------------- PRODUCTS ----------------
def reload_products():
    global products
    products = load_json(PRODUCTS_FILE, DEFAULT_PRODUCTS)


def build_products_keyboard():
    keyboard = []
    for product_id, product in products.items():
        stock = get_stock(product["file"])
        if stock <= 0:
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {product['name']} (₹{product['price']}) | Out of stock",
                    callback_data=f"outofstock_{product_id}",
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    f"🛍️ {product['name']} (₹{product['price']}) | Stock: {stock}",
                    callback_data=f"select_{product_id}",
                )
            ])
    return keyboard


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.message.from_user)
    keyboard = [
        [InlineKeyboardButton("🛒 Buy", callback_data="menu_buy")],
        [InlineKeyboardButton("📦 My Orders", callback_data="menu_history")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ]
    await update.message.reply_text("Welcome! Choose option:", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------- MENU ----------------
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)

    if query.data == "menu_buy":
        reload_products()
        keyboard = build_products_keyboard()
        if not keyboard:
            await query.message.reply_text("No products available right now")
            return
        await query.message.reply_text("Select product:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "menu_history":
        await show_user_orders(query.message.chat_id, context)

    elif query.data == "menu_help":
        await query.message.reply_text(
            "❓ Need Help?\n\n"
            "📩 Contact: @myntracodes\n\n"
            "Use Buy button to purchase"
        )


# ---------------- USER HISTORY ----------------
async def show_user_orders(user_id, context):
    history = load_order_history()
    user_orders = [x for x in history if x.get("user_id") == user_id]

    if not user_orders:
        await context.bot.send_message(user_id, "No order history found")
        return

    lines = ["📦 Your Order History\n"]
    for item in user_orders[-10:][::-1]:
        lines.append(
            f"🧾 {item.get('product_name')}\n"
            f"Qty: {item.get('qty')} | Total: ₹{item.get('total')}\n"
            f"Status: {item.get('status')}\n"
            f"Time: {item.get('created_at')}\n"
        )

    await context.bot.send_message(user_id, "\n".join(lines))


# ---------------- SELECT PRODUCT ----------------
async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)

    product_id = query.data.split("_", 1)[1]
    reload_products()

    if product_id not in products:
        await query.message.reply_text("Invalid product")
        return

    stock = get_stock(products[product_id]["file"])
    if stock <= 0:
        await query.message.reply_text("This product is out of stock")
        return

    context.user_data["product"] = product_id

    keyboard = [
        [InlineKeyboardButton("1", callback_data="qty_1"),
         InlineKeyboardButton("2", callback_data="qty_2"),
         InlineKeyboardButton("3", callback_data="qty_3")],
        [InlineKeyboardButton("5", callback_data="qty_5"),
         InlineKeyboardButton("10", callback_data="qty_10")],
        [InlineKeyboardButton("✍️ Custom", callback_data="qty_custom")]
    ]

    await query.message.reply_text("Select quantity:", reply_markup=InlineKeyboardMarkup(keyboard))


async def out_of_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query, text="This product is out of stock", show_alert=True)


# ---------------- SELECT QTY ----------------
async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)

    if query.data == "qty_custom":
        context.user_data["awaiting_qty"] = True
        await query.message.reply_text("Enter custom quantity:")
        return

    qty = int(query.data.split("_")[1])
    context.user_data["qty"] = qty

    await process_order(query.message, context, qty)


# ---------------- CUSTOM QTY ----------------
async def custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)

        if qty <= 0:
            await update.message.reply_text("Invalid quantity")
            return

        context.user_data["awaiting_qty"] = False
        context.user_data["qty"] = qty

        await process_order(update.message, context, qty)

    except:
        await update.message.reply_text("Send number only")


# ---------------- ORDER ----------------
async def process_order(message, context, qty):
    product_id = context.user_data.get("product")
    reload_products()

    if product_id not in products:
        await message.reply_text("Invalid product")
        return

    product = products[product_id]
    stock = get_stock(product["file"])

    if stock <= 0:
        await message.reply_text("This product is out of stock")
        return

    if qty > stock:
        await message.reply_text(f"Only {stock} left")
        return

    total = product["price"] * qty
    context.user_data["total"] = total

    if total >= 400:
        upi = HIGH_UPI
        qr = HIGH_QR
    else:
        upi = LOW_UPI
        qr = LOW_QR

    await message.reply_text(
        f"🧾 Order Summary\n\n"
        f"{product['name']}\nQty: {qty}\nStock: {stock}\nTotal: ₹{total}\n\nUPI: {upi}"
    )

    try:
        with open(qr, "rb") as photo:
            await context.bot.send_photo(message.chat_id, photo)
    except:
        await message.reply_text("QR not found")

    await message.reply_text("Send screenshot after payment")


# ---------------- SCREENSHOT ----------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    product_id = context.user_data.get("product")
    qty = context.user_data.get("qty")
    total = context.user_data.get("total", 0)

    if not product_id or not qty or product_id not in products:
        await update.message.reply_text("Please select a product first")
        return

    product = products[product_id]

    add_order_history({
        "user_id": user.id,
        "username": user.username,
        "name": user.first_name,
        "product_id": product_id,
        "product_name": product["name"],
        "qty": qty,
        "total": total,
        "status": "payment_sent",
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
    })

    for admin in ALL_ADMINS:
        if admin in MAIN_ADMINS:
            keyboard = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}_{product_id}_{qty}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}_{product_id}_{qty}"),
            ]]
            markup = InlineKeyboardMarkup(keyboard)
        else:
            markup = None

        await context.bot.send_message(
            admin,
            f"New Order\n"
            f"User: {user.first_name}\n"
            f"Username: @{user.username if user.username else 'NoUsername'}\n"
            f"Product: {product['name']}\n"
            f"Qty: {qty}\n"
            f"Total: ₹{total}",
            reply_markup=markup,
        )

        await context.bot.forward_message(admin, update.message.chat_id, update.message.message_id)

    await update.message.reply_text("Waiting for approval")


# ---------------- ADMIN ----------------
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)

    if query.from_user.id not in MAIN_ADMINS:
        await query.answer("Not allowed", show_alert=True)
        return

    data = query.data.split("_")
    action = data[0]
    user_id = int(data[1])

    if action == "approve":
        product_id = data[2]
        qty = int(data[3])

        reload_products()
        if product_id not in products:
            await query.message.reply_text("Invalid product")
            return

        stock = get_stock(products[product_id]["file"])
        if stock <= 0 or stock < qty:
            update_order_status(user_id, product_id, qty, "failed_no_stock")
            await context.bot.send_message(user_id, "Sorry, product went out of stock")
            await query.message.reply_text("No stock")
            return

        codes = get_codes(products[product_id]["file"], qty)
        if not codes:
            update_order_status(user_id, product_id, qty, "failed_no_stock")
            await query.message.reply_text("No stock")
            return

        update_order_status(user_id, product_id, qty, "approved")
        await context.bot.send_message(user_id, "Codes:\n" + "\n".join(codes))
        await query.message.reply_text("Delivered")

    elif action == "reject":
        product_id = data[2] if len(data) > 2 else None
        qty = int(data[3]) if len(data) > 3 else 0
        if product_id:
            update_order_status(user_id, product_id, qty, "rejected")
        await context.bot.send_message(user_id, "Payment rejected")
        await query.message.reply_text("Rejected")


# ---------------- ADD CODES ----------------
async def add_codes_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in MAIN_ADMINS:
        return

    try:
        reload_products()
        product_id = context.args[0]

        if product_id not in products:
            await update.message.reply_text("Invalid product ID")
            return

        context.user_data["adding_codes"] = product_id
        await update.message.reply_text("Send codes (one per line)")

    except:
        await update.message.reply_text("Usage: /addcodes p1")


async def add_codes_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = context.user_data.get("adding_codes")

    if not product_id:
        return False

    reload_products()
    if product_id not in products:
        context.user_data["adding_codes"] = None
        await update.message.reply_text("Invalid product ID")
        return True

    file = products[product_id]["file"]
    codes = [code.strip() for code in update.message.text.strip().split("\n") if code.strip()]

    with open(file, "a", encoding="utf-8") as f:
        for code in codes:
            f.write(code + "\n")

    context.user_data["adding_codes"] = None
    await update.message.reply_text(f"Added {len(codes)} codes")
    return True


# ---------------- ADD PRODUCT ----------------
async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in MAIN_ADMINS:
        return

    try:
        # Format: /addproduct p3|Myntra ₹200 Off|60|myntra200.txt
        raw = " ".join(context.args)
        product_id, name, price, filename = [x.strip() for x in raw.split("|", 3)]
        price = int(price)

        reload_products()
        products[product_id] = {
            "name": name,
            "price": price,
            "file": filename,
        }
        save_json(PRODUCTS_FILE, products)

        await update.message.reply_text(
            f"Product added\nID: {product_id}\nName: {name}\nPrice: ₹{price}\nFile: {filename}"
        )
    except:
        await update.message.reply_text(
            "Usage:\n/addproduct p3|Myntra ₹200 Off|60|myntra200.txt"
        )


# ---------------- LIST PRODUCTS ----------------
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reload_products()
    lines = ["📦 Products\n"]
    for product_id, product in products.items():
        lines.append(
            f"{product_id} | {product['name']} | ₹{product['price']} | Stock: {get_stock(product['file'])}"
        )
    await update.message.reply_text("\n".join(lines))


# ---------------- HISTORY COMMAND ----------------
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_user_orders(update.message.chat_id, context)


async def admin_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in MAIN_ADMINS:
        return

    history = load_order_history()
    if not history:
        await update.message.reply_text("No orders found")
        return

    lines = ["📊 All Orders\n"]
    for item in history[-25:][::-1]:
        username = item.get("username")
        username_text = f"@{username}" if username else "NoUsername"
        lines.append(
            f"👤 {item.get('name', 'Unknown')} | {username_text}\n"
            f"🆔 {item.get('user_id')}\n"
            f"📦 {item.get('product_name')}\n"
            f"🔢 Qty: {item.get('qty')} | ₹{item.get('total')}\n"
            f"📌 Status: {item.get('status')}\n"
            f"🕒 {item.get('created_at')}\n"
        )

    await update.message.reply_text("\n".join(lines))


# ---------------- BROADCAST ----------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in MAIN_ADMINS:
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast your message")
        return

    message = " ".join(context.args)
    users = load_json(USERS_FILE, [])

    if not users:
        await update.message.reply_text("No users found")
        return

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await context.bot.send_message(user_id, message)
            sent += 1
        except:
            failed += 1

    await update.message.reply_text(f"Broadcast completed\nSent: {sent}\nFailed: {failed}")


# ---------------- TEXT ----------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("adding_codes"):
        handled = await add_codes_save(update, context)
        if handled:
            return

    if context.user_data.get("awaiting_qty"):
        await custom_quantity(update, context)
        return


# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addcodes", add_codes_start))
app.add_handler(CommandHandler("addproduct", add_product))
app.add_handler(CommandHandler("products", list_products))
app.add_handler(CommandHandler("history", history_command))
app.add_handler(CommandHandler("allorders", admin_history))
app.add_handler(CommandHandler("broadcast", broadcast))

app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_"))
app.add_handler(CallbackQueryHandler(out_of_stock, pattern="^outofstock_"))
app.add_handler(CallbackQueryHandler(select_product, pattern="^select_"))
app.add_handler(CallbackQueryHandler(select_quantity, pattern="^qty_"))
app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve_|reject_)"))

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
