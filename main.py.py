from flask import Flask, render_template, request, redirect, url_for, send_file, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email
import pandas as pd
from io import BytesIO
from flask_migrate import Migrate
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
# Credenciales permitidas
USUARIOS_PERMITIDOS = {
    'mariela.puebla@uvm.cl': '123456789',
    'pamela.briceno@uvm.cl': '123456789',
    'boris.herrera@uvm.cl': '123456789'
}
db = SQLAlchemy(app)
migrate = Migrate(app, db)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))  # Redirigir al inicio de sesión
        return f(*args, **kwargs)
    return decorated_function

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    apellido_paterno = db.Column(db.String(50), nullable=False)
    apellido_materno = db.Column(db.String(50), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    cargo = db.Column(db.String(50), nullable=False)
    institucion = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    correo_secretaria = db.Column(db.String(100), nullable=True)  # Campo opcional

class UsuarioForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(message="El nombre es obligatorio.")])
    apellido_paterno = StringField('Apellido Paterno', validators=[DataRequired(message="El apellido paterno es obligatorio.")])
    apellido_materno = StringField('Apellido Materno', validators=[DataRequired(message="El apellido materno es obligatorio.")])
    correo = StringField('Correo', validators=[DataRequired(), Email(message="El correo no es válido.")])
    correo_secretaria = StringField('Correo de Secretaría')
    cargo = StringField('Cargo', validators=[DataRequired(message="El cargo es obligatorio.")])
    institucion = StringField('Institución', validators=[DataRequired(message="La institución es obligatoria.")])
    telefono = StringField('Teléfono', validators=[DataRequired(message="El teléfono es obligatorio.")])
    submit = SubmitField('Guardar')

class FiltroForm(FlaskForm):
    institucion = SelectField('Institución', choices=[])
    cargo = SelectField('Cargo', choices=[])
    submit = SubmitField('Filtrar')

@app.route('/')
@login_required
def index():
    form = FiltroForm()

    # Obtener valores únicos para los filtros
    instituciones = db.session.query(Usuario.institucion.distinct()).all()
    cargos = db.session.query(Usuario.cargo.distinct()).all()

    # Agregar opciones "Todas" y "Todos"
    form.institucion.choices = [('','Todas')] + [(i[0], i[0]) for i in instituciones if i[0] != '']
    form.cargo.choices = [('','Todos')] + [(c[0], c[0]) for c in cargos if c[0] != '']

    query = Usuario.query

    # Obtener filtros seleccionados (pueden ser múltiples)
    institucion_filtro = request.args.getlist('institucion')
    cargo_filtro = request.args.getlist('cargo')

    if institucion_filtro and 'Todas' not in institucion_filtro:
        query = query.filter(Usuario.institucion.in_(institucion_filtro))
    if cargo_filtro and 'Todos' not in cargo_filtro:
        query = query.filter(Usuario.cargo.in_(cargo_filtro))

    usuarios = query.all()

    # Preparar URLs para eliminar filtros específicos
    institucion_urls = {
        institucion: url_for('index', 
                             institucion=[f for f in institucion_filtro if f != institucion], 
                             cargo=cargo_filtro)
        for institucion in institucion_filtro
    }

    cargo_urls = {
        cargo: url_for('index', 
                       institucion=institucion_filtro, 
                       cargo=[f for f in cargo_filtro if f != cargo])
        for cargo in cargo_filtro
    }

    return render_template('index.html', 
                           usuarios=usuarios, 
                           form=form, 
                           institucion_filtro=institucion_filtro, 
                           cargo_filtro=cargo_filtro,
                           institucion_urls=institucion_urls,
                           cargo_urls=cargo_urls)



@app.route('/agregar', methods=['GET', 'POST'])
@login_required
def agregar():
    form = UsuarioForm()
    if form.validate_on_submit():
        nuevo_usuario = Usuario(
            nombre=form.nombre.data,
            apellido_paterno=form.apellido_paterno.data,
            apellido_materno=form.apellido_materno.data,
            correo=form.correo.data,
            correo_secretaria=form.correo_secretaria.data,
            cargo=form.cargo.data,
            institucion=form.institucion.data,
            telefono=form.telefono.data
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('agregar.html', form=form)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    usuario = Usuario.query.get_or_404(id)
    form = UsuarioForm(obj=usuario)
    if form.validate_on_submit():
        form.populate_obj(usuario)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('editar.html', form=form)

@app.route('/eliminar/<int:id>')
def eliminar(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/exportar')
def exportar():
    query = Usuario.query

    institucion = request.args.get('institucion')
    cargo = request.args.get('cargo')

    if institucion:
        query = query.filter_by(institucion=institucion)
    if cargo:
        query = query.filter_by(cargo=cargo)

    usuarios = query.all()

    # Crear DataFrame
    data = {
        'Nombre': [u.nombre for u in usuarios],
        'Apellido Paterno': [u.apellido_paterno for u in usuarios],
        'Apellido Materno': [u.apellido_materno for u in usuarios],
        'Cargo': [u.cargo for u in usuarios],
        'Institución': [u.institucion for u in usuarios],
        'Correo': [u.correo for u in usuarios],
        'Correo Secretaría': [u.correo_secretaria for u in usuarios],
        'Teléfono': [u.telefono for u in usuarios]  
    }

    df = pd.DataFrame(data)

    # Crear archivo Excel usando un contexto with
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Usuarios')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='usuarios.xlsx'
    )



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')

        # Verificar si el correo y la contraseña son válidos
        if correo in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[correo] == contrasena:
            session['usuario'] = correo  # Guardar el correo en la sesión
            return redirect(url_for('index'))
        else:
            error = "Correo o contraseña incorrectos"
            return render_template('login.html', error=error)

    # Mostrar el formulario de inicio de sesión
    return render_template('login.html', error=None)

@app.route('/logout')
def logout():
    session.pop('usuario', None)  # Eliminar el usuario de la sesión
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 - Página no encontrada</h1><p>No tienes permiso para acceder a esta página.</p>", 404
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)