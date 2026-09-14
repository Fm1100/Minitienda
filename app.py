from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'mi_clave_secreta_super_segura'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('tienda.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'cliente'
        )
    ''')
    
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'cliente'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio REAL NOT NULL,
            stock INTEGER NOT NULL,
            categoria_id INTEGER,
            imagen TEXT,
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    ''')
    
    # Tablas para el historial de pedidos y compras
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            direccion TEXT NOT NULL,
            telefono TEXT NOT NULL,
            total REAL NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS detalle_pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            producto_nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            cantidad INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos (id)
        )
    ''')
    
    # Inserción automática de usuarios de prueba
    admin_email = 'admin@gmail.com'
    cliente_email = 'cliente@gmail.com'
    
    admin_existe = conn.execute('SELECT * FROM usuarios WHERE email = ?', (admin_email,)).fetchone()
    if not admin_existe:
        pass_admin = generate_password_hash('1234')
        conn.execute('INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)',
                     ('Administrador', admin_email, pass_admin, 'admin'))
        
    cliente_existe = conn.execute('SELECT * FROM usuarios WHERE email = ?', (cliente_email,)).fetchone()
    if not cliente_existe:
        pass_cliente = generate_password_hash('5678')
        conn.execute('INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)',
                     ('Cliente Prueba', cliente_email, pass_cliente, 'cliente'))

    conn.commit()
    conn.close()

init_db()

@app.context_processor
def inject_cart_count():
    carrito = session.get('carrito', {})
    total_items = sum(carrito.values())
    return dict(total_carrito=total_items)

# --- RUTA DE INICIO ---

@app.route('/')
def index():
    conn = get_db_connection()
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    productos_db = conn.execute('''
        SELECT productos.*, COALESCE(categorias.nombre, 'Sin categoría') AS nombre_categoria 
        FROM productos 
        LEFT JOIN categorias ON productos.categoria_id = categorias.id
    ''').fetchall()
    conn.close()
    return render_template('index.html', categorias_html=categorias_db, productos_html=productos_db)

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        rol = 'cliente'
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO usuarios (nombre, email, password, rol) VALUES (?, ?, ?, ?)',
                         (nombre, email, hashed_password, rol))
            conn.commit()
            conn.close()
            flash("¡Cuenta creada con éxito! Ahora puedes iniciar sesión.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash("El correo electrónico ya está registrado.", "error")
            return redirect(url_for('registro'))
        
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if usuario and check_password_hash(usuario['password'], password):
            session['usuario_id'] = usuario['id']
            session['nombre_usuario'] = usuario['nombre']
            session['rol'] = usuario['rol']
            flash(f"¡Bienvenido de nuevo, {usuario['nombre']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Correo o contraseña incorrectos.", "error")
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for('index'))

# --- RUTAS DE CATEGORÍAS (Solo Administrador) ---

@app.route('/categorias', methods=['GET', 'POST'])
def categorias():
    if session.get('rol') != 'admin':
        flash("Acceso denegado. Debes iniciar sesión como administrador.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if request.method == 'POST':
        nombre_categoria = request.form['nombre']
        conn.execute('INSERT INTO categorias (nombre) VALUES (?)', (nombre_categoria,))
        conn.commit()
        conn.close()
        flash("Categoría creada con éxito.", "success")
        return redirect(url_for('categorias'))
    
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('categorias.html', categorias_html=categorias_db)

@app.route('/categorias/eliminar/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    if session.get('rol') != 'admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('index'))

    conn = get_db_connection()
    conn.execute('DELETE FROM categorias WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Categoría eliminada.", "success")
    return redirect(url_for('categorias'))

@app.route('/categorias/editar/<int:id>', methods=['GET', 'POST'])
def editar_categoria(id):
    if session.get('rol') != 'admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('index'))

    conn = get_db_connection()
    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        conn.execute('UPDATE categorias SET nombre = ? WHERE id = ?', (nuevo_nombre, id))
        conn.commit()
        conn.close()
        flash("Categoría actualizada con éxito.", "success")
        return redirect(url_for('categorias'))
    
    categoria = conn.execute('SELECT * FROM categorias WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('editar_categoria.html', categoria=categoria)

@app.route('/categoria/<int:id>/productos')
def productos_por_categoria(id):
    conn = get_db_connection()
    categoria = conn.execute('SELECT * FROM categorias WHERE id = ?', (id,)).fetchone()
    productos_db = conn.execute('''
        SELECT productos.*, categorias.nombre AS nombre_categoria 
        FROM productos 
        JOIN categorias ON productos.categoria_id = categorias.id
        WHERE productos.categoria_id = ?
    ''', (id,)).fetchall()
    conn.close()
    return render_template('productos_categoria.html', categoria=categoria, productos_html=productos_db)

# --- RUTAS DE PRODUCTOS (Protegidas estrictamente para Admin) ---

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    if session.get('rol') != 'admin':
        flash("Acceso denegado. Se requiere cuenta de administrador.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        categoria_id = request.form['categoria_id']
        
        imagen_filename = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file.filename != '':
                imagen_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename))
        
        conn.execute('''
            INSERT INTO productos (nombre, descripcion, precio, stock, categoria_id, imagen) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre, descripcion, precio, stock, categoria_id, imagen_filename))
        conn.commit()
        conn.close()
        flash("Producto creado exitosamente.", "success")
        return redirect(url_for('productos'))
    
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    productos_db = conn.execute('''
        SELECT productos.*, categorias.nombre AS nombre_categoria 
        FROM productos 
        JOIN categorias ON productos.categoria_id = categorias.id
    ''').fetchall()
    conn.close()
    return render_template('productos.html', categorias_html=categorias_db, productos_html=productos_db)

@app.route('/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if session.get('rol') != 'admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('index'))

    conn = get_db_connection()
    conn.execute('DELETE FROM productos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Producto eliminado.", "success")
    return redirect(url_for('productos'))

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if session.get('rol') != 'admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('index'))

    conn = get_db_connection()
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        categoria_id = request.form['categoria_id']
        
        imagen_filename = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file.filename != '':
                imagen_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename))
        
        if imagen_filename:
            conn.execute('''
                UPDATE productos 
                SET nombre = ?, descripcion = ?, precio = ?, stock = ?, categoria_id = ?, imagen = ? 
                WHERE id = ?
            ''', (nombre, descripcion, precio, stock, categoria_id, imagen_filename, id))
        else:
            conn.execute('''
                UPDATE productos 
                SET nombre = ?, descripcion = ?, precio = ?, stock = ?, categoria_id = ? 
                WHERE id = ?
            ''', (nombre, descripcion, precio, stock, categoria_id, id))
            
        conn.commit()
        conn.close()
        flash("Producto actualizado con éxito.", "success")
        return redirect(url_for('productos'))
    
    producto = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    categorias_db = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('editar_producto.html', producto=producto, categorias_html=categorias_db)

# --- RUTAS DEL CARRITO Y CHECKOUT ---

@app.route('/carrito/agregar/<int:id>', methods=['POST', 'GET'])
def agregar_carrito(id):
    conn = get_db_connection()
    producto = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if not producto:
        flash("Producto no encontrado.", "error")
        return redirect(url_for('index'))

    if 'carrito' not in session:
        session['carrito'] = {}
        
    carrito = session['carrito']
    id_str = str(id)
    
    if request.method == 'POST':
        cantidad = int(request.form.get('cantidad', 1))
    else:
        cantidad = 1
        
    if cantidad < 1:
        cantidad = 1
        
    cantidad_actual = carrito.get(id_str, 0)
    if (cantidad_actual + cantidad) > producto['stock']:
        flash(f"No hay suficiente stock disponible. Stock máximo: {producto['stock']}.", "error")
        return redirect(url_for('index'))
        
    if id_str in carrito:
        carrito[id_str] += cantidad
    else:
        carrito[id_str] = cantidad
        
    session.modified = True
    flash("Producto agregado al carrito.", "success")
    return redirect(request.referrer or url_for('ver_carrito'))

@app.route('/carrito/disminuir/<int:id>')
def disminuir_carrito(id):
    if 'carrito' in session:
        id_str = str(id)
        if id_str in session['carrito']:
            if session['carrito'][id_str] > 1:
                session['carrito'][id_str] -= 1
            else:
                session['carrito'].pop(id_str)
            session.modified = True
    return redirect(url_for('ver_carrito'))

@app.route('/carrito/actualizar/<int:id>', methods=['POST'])
def actualizar_carrito(id):
    if 'carrito' in session:
        id_str = str(id)
        if id_str in session['carrito']:
            try:
                nueva_cantidad = int(request.form.get('cantidad', 1))
                conn = get_db_connection()
                producto = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
                conn.close()
                
                if producto and nueva_cantidad <= producto['stock'] and nueva_cantidad > 0:
                    session['carrito'][id_str] = nueva_cantidad
                    session.modified = True
                    flash("Carrito actualizado.", "success")
                else:
                    flash("Cantidad no válida o supera el stock.", "error")
            except ValueError:
                pass
    return redirect(url_for('ver_carrito'))

@app.route('/carrito/remover/<int:id>')
def remover_producto_carrito(id):
    if 'carrito' in session:
        id_str = str(id)
        if id_str in session['carrito']:
            session['carrito'].pop(id_str)
            session.modified = True
            flash("Producto eliminado del carrito.", "success")
    return redirect(url_for('ver_carrito'))

@app.route('/carrito')
def ver_carrito():
    if 'carrito' not in session or not session['carrito']:
        return render_template('carrito.html', productos_carrito=[], total=0)
    
    conn = get_db_connection()
    carrito = session['carrito']
    productos_carrito = []
    total = 0
    
    for producto_id, cantidad in carrito.items():
        producto = conn.execute('SELECT * FROM productos WHERE id = ?', (producto_id,)).fetchone()
        if producto:
            subtotal = producto['precio'] * cantidad
            total += subtotal
            productos_carrito.append({
                'id': producto['id'],
                'nombre': producto['nombre'],
                'precio': producto['precio'],
                'imagen': producto['imagen'],
                'stock': producto['stock'],
                'cantidad': cantidad,
                'subtotal': subtotal
            })
    conn.close()
    return render_template('carrito.html', productos_carrito=productos_carrito, total=total)

@app.route('/carrito/limpiar')
def limpiar_carrito():
    session.pop('carrito', None)
    flash("El carrito ha sido vaciado.", "success")
    return redirect(url_for('ver_carrito'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para finalizar la compra.", "error")
        return redirect(url_for('login'))
        
    if 'carrito' not in session or not session['carrito']:
        return redirect(url_for('ver_carrito'))
        
    if request.method == 'POST':
        direccion = request.form.get('direccion')
        telefono = request.form.get('telefono')
        usuario_id = session['usuario_id']
        
        conn = get_db_connection()
        carrito = session['carrito']
        
        total_pedido = 0
        productos_a_procesar = []
        
        for producto_id, cantidad in carrito.items():
            producto = conn.execute('SELECT * FROM productos WHERE id = ?', (producto_id,)).fetchone()
            if producto:
                if producto['stock'] < cantidad:
                    conn.close()
                    flash(f"Lo sentimos, el producto '{producto['nombre']}' ya no tiene suficiente stock.", "error")
                    return redirect(url_for('ver_carrito'))
                
                subtotal = producto['precio'] * cantidad
                total_pedido += subtotal
                productos_a_procesar.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'subtotal': subtotal
                })
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pedidos (usuario_id, direccion, telefono, total) 
            VALUES (?, ?, ?, ?)
        ''', (usuario_id, direccion, telefono, total_pedido))
        pedido_id = cursor.lastrowid
        
        for item in productos_a_procesar:
            prod = item['producto']
            cant = item['cantidad']
            sub = item['subtotal']
            
            cursor.execute('''
                INSERT INTO detalle_pedidos (pedido_id, producto_nombre, precio, cantidad, subtotal) 
                VALUES (?, ?, ?, ?, ?)
            ''', (pedido_id, prod['nombre'], prod['precio'], cant, sub))
            
            nuevo_stock = prod['stock'] - cant
            cursor.execute('UPDATE productos SET stock = ? WHERE id = ?', (nuevo_stock, prod['id']))
        
        conn.commit()
        conn.close()
        
        session.pop('carrito', None)
        flash("¡Compra procesada con éxito!", "success")
        return render_template('compra_exitosa.html')
        
    return render_template('checkout.html')

@app.route('/mis-compras')
def mis_compras():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para ver tus compras.", "error")
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    conn = get_db_connection()
    
    pedidos_db = conn.execute('''
        SELECT * FROM pedidos WHERE usuario_id = ? ORDER BY fecha DESC
    ''', (usuario_id,)).fetchall()
    
    historial = []
    for pedido in pedidos_db:
        detalles = conn.execute('''
            SELECT * FROM detalle_pedidos WHERE pedido_id = ?
        ''', (pedido['id'],)).fetchall()
        
        historial.append({
            'pedido': pedido,
            'detalles': detalles
        })
        
    conn.close()
    return render_template('mis_compras.html', historial=historial)

if __name__ == '__main__':
    app.run(debug=True)