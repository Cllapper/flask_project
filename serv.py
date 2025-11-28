from flask import Flask, render_template, request, redirect, url_for, abort, session, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'change_me'
db = SQLAlchemy(app)

post_tags = db.Table(
    'post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    posts = relationship('Post', back_populates='category')

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(80), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    category = relationship('Category', back_populates='posts')
    tags = relationship('Tag', secondary=post_tags, back_populates='posts')

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    posts = relationship('Post', secondary=post_tags, back_populates='tags')

def seed_db():
    if User.query.count() == 0:
        u = User(username='admin')
        u.set_password('admin')
        db.session.add(u)
    if Category.query.count() == 0:
        c1 = Category(name='Навчання')
        c2 = Category(name='Робота')
        c3 = Category(name='Особисте')
        db.session.add_all([c1, c2, c3])
        t1 = Tag(name='Flask')
        t2 = Tag(name='Jinja')
        t3 = Tag(name='Python')
        db.session.add_all([t1, t2, t3])
        p1 = Post(title='Перший пост', author='Bogdan', body='Пост із бази даних', category=c1, tags=[t1, t2])
        p2 = Post(title='Другий пост', author='Admin', body='Flask-SQLAlchemy працює', category=c2, tags=[t3])
        db.session.add_all([p1, p2])
    db.session.commit()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, 'current_user', None):
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped

@app.before_request
def load_current_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.current_user = None
    else:
        g.current_user = User.query.get(user_id)

@app.context_processor
def inject_user():
    return {'current_user': getattr(g, 'current_user', None)}

@app.route('/')
def main():
    posts = Post.query.order_by(Post.id.desc()).all()
    posts_view = []
    for p in posts:
        posts_view.append({
            'id': p.id,
            'title': p.title,
            'author': p.author,
            'body': p.body,
            'tags': [t.name for t in p.tags],
            'category_name': p.category.name if p.category else ''
        })
    return render_template('main.html', posts=posts_view)

@app.route('/about')
def about():
    categories = Category.query.order_by(Category.name).all()
    categories_view = []
    for c in categories:
        categories_view.append({'name': c.name, 'posts_count': len(c.posts)})
    return render_template('about.html', project='Блог-демо', posts_count=Post.query.count(), categories=categories_view)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()
        if not username or not password:
            error = 'Введіть логін і пароль'
        elif password != confirm:
            error = 'Паролі не співпадають'
        elif User.query.filter_by(username=username).first():
            error = 'Користувач уже існує'
        else:
            u = User(username=username)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            session['user_id'] = u.id
            return redirect(url_for('main'))
    return render_template('auth.html', mode='register', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('main'))
        else:
            error = 'Невірний логін або пароль'
    return render_template('auth.html', mode='login', error=error)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('main'))

@app.route('/posts/new', methods=['GET', 'POST'])
@login_required
def create_post():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        body = request.form.get('body', '').strip()
        tags_raw = request.form.get('tags', '').strip()
        category_id = request.form.get('category_id', '').strip()
        category_id_val = int(category_id) if category_id else None
        if not title or not author or not body:
            post_data = {'title': title, 'author': author, 'body': body, 'tags': tags_raw, 'category_id': category_id_val}
            return render_template('post_form.html', mode='create', post=post_data, categories=categories)
        tag_names = [x.strip() for x in tags_raw.split(',') if x.strip()] if tags_raw else []
        tag_objs = []
        for name in tag_names:
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
            tag_objs.append(tag)
        category = Category.query.get(category_id_val) if category_id_val else None
        post = Post(title=title, author=author, body=body, tags=tag_objs, category=category)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('main'))
    post_data = {'title': '', 'author': '', 'body': '', 'tags': '', 'category_id': None}
    return render_template('post_form.html', mode='create', post=post_data, categories=Category.query.order_by(Category.name).all())

@app.route('/posts/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        abort(404)
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        body = request.form.get('body', '').strip()
        tags_raw = request.form.get('tags', '').strip()
        category_id = request.form.get('category_id', '').strip()
        category_id_val = int(category_id) if category_id else None
        if not title or not author or not body:
            post_data = {
                'id': post.id,
                'title': title,
                'author': author,
                'body': body,
                'tags': tags_raw if tags_raw else ', '.join([t.name for t in post.tags]),
                'category_id': category_id_val
            }
            return render_template('post_form.html', mode='edit', post=post_data, categories=categories)
        post.title = title
        post.author = author
        post.body = body
        post.tags.clear()
        tag_names = [x.strip() for x in tags_raw.split(',') if x.strip()] if tags_raw else []
        for name in tag_names:
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
            post.tags.append(tag)
        post.category = Category.query.get(category_id_val) if category_id_val else None
        db.session.commit()
        return redirect(url_for('main'))
    post_data = {
        'id': post.id,
        'title': post.title,
        'author': post.author,
        'body': post.body,
        'tags': ', '.join([t.name for t in post.tags]),
        'category_id': post.category.id if post.category else None
    }
    return render_template('post_form.html', mode='edit', post=post_data, categories=categories)

@app.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        abort(404)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('main'))

with app.app_context():
    db.create_all()
    seed_db()

if __name__ == '__main__':
    app.run(debug=True)
