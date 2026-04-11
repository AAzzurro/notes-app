import os
import re
import json
import urllib.parse
from datetime import datetime, timezone, timedelta

from flask import Flask, Response, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 模板过滤器

@app.template_filter('local_time')
def local_time(dt):
    if dt is None:
        return ''
    beijing = timezone(timedelta(hours=8))
    return dt.replace(tzinfo=timezone.utc).astimezone(beijing).strftime('%Y-%m-%d %H:%M')


@app.template_filter('highlight')
def highlight(text, query):
    if not query:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(f'<mark>{query}</mark>', text)


@app.template_filter('preview')
def preview(content, query):
    if not query:
        return content[:150] + '...'
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:150] + '...'
    start = max(0, idx - 60)
    end = min(len(content), idx + 60)
    snippet = content[start:end]
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    snippet = pattern.sub(f'<mark>{query}</mark>', snippet)
    return ('...' if start > 0 else '') + snippet + ('...' if end < len(content) else '')

# 数据模型

note_tags = db.Table(
    'note_tags',
    db.Column('note_id', db.Integer, db.ForeignKey('note.id'), primary_key=True),
    db.Column('tag_id',  db.Integer, db.ForeignKey('tag.id'),  primary_key=True),
)


class Tag(db.Model):
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class Folder(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes   = db.relationship('Note', backref='folder', lazy=True)


class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    notes    = db.relationship('Note', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)


class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id    = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=False)

class Note(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)  # 手动在 edit 时刷新
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id  = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    is_public  = db.Column(db.Boolean, default=False)
    tags       = db.relationship('Tag', secondary=note_tags, backref='notes')
    comments   = db.relationship('Comment', backref='note', lazy=True, order_by='Comment.created_at.desc()')

# 辅助函数

def get_or_404(model, pk):
    """兼容 SQLAlchemy 2.x 的 get_or_404。"""
    obj = db.session.get(model, pk)
    if obj is None:
        from flask import abort
        abort(404)
    return obj


def sync_tags(note, raw_tags: str):
    """将逗号分隔的标签字符串同步到 note.tags。"""
    tag_names = [t.strip() for t in raw_tags.split(',') if t.strip()]
    note.tags = []
    for name in tag_names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        note.tags.append(tag)

# 用户认证

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            error = '用户名已存在'
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            error = '用户名或密码错误'
        else:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html', error=error)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    error = success = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'username':
            new_username = request.form['username'].strip()
            if not new_username:
                error = '用户名不能为空'
            elif User.query.filter_by(username=new_username).first():
                error = '用户名已存在'
            else:
                current_user.username = new_username
                db.session.commit()
                success = '用户名修改成功'
        elif action == 'password':
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            if not check_password_hash(current_user.password, old_password):
                error = '原密码错误'
            elif not new_password:
                error = '新密码不能为空'
            else:
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                success = '密码修改成功'
    return render_template('profile.html', error=error, success=success)

# 主页

@app.route('/')
@login_required
def index():
    folder_id = request.args.get('folder_id')
    tag_id    = request.args.get('tag_id')

    q = Note.query.filter_by(user_id=current_user.id)
    if folder_id:
        q = q.filter_by(folder_id=folder_id)
    if tag_id:
        tag = db.session.get(Tag, int(tag_id))
        if tag:
            q = q.filter(Note.tags.contains(tag))

    notes   = q.order_by(Note.created_at.desc()).all()
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    tags    = (Tag.query
               .join(note_tags)
               .join(Note)
               .filter(Note.user_id == current_user.id)
               .distinct().all())

    return render_template(
        'index.html', notes=notes, folders=folders, tags=tags,
        current_folder_id=int(folder_id) if folder_id else None,
        current_tag_id=int(tag_id) if tag_id else None,
    )

# 笔记

@app.route('/notes/new', methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        title   = request.form['title']
        content = request.form['content']
        if not title.strip():
            folders = Folder.query.filter_by(user_id=current_user.id).all()
            return render_template('new_note.html', error='标题不能为空', folders=folders)
        note = Note(
            title=title, content=content,
            user_id=current_user.id,
            folder_id=request.form.get('folder_id') or None,
        )
        sync_tags(note, request.form.get('tags', ''))
        db.session.add(note)
        db.session.commit()
        return redirect(url_for('index'))
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    return render_template('new_note.html', folders=folders)


@app.route('/notes/<int:note_id>')
@login_required
def view_note(note_id):
    note = get_or_404(Note, note_id)
    return render_template('view_note.html', note=note)


@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = get_or_404(Note, note_id)
    if request.method == 'POST':
        note.title      = request.form['title']
        note.content    = request.form['content']
        note.folder_id  = request.form.get('folder_id') or None
        note.updated_at = datetime.utcnow()
        sync_tags(note, request.form.get('tags', ''))
        db.session.commit()
        return redirect(url_for('view_note', note_id=note.id))
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    return render_template('edit_note.html', note=note, folders=folders)


@app.route('/notes/<int:note_id>/delete')
@login_required
def delete_note(note_id):
    note = get_or_404(Note, note_id)
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/notes/<int:note_id>/toggle_public')
@login_required
def toggle_public(note_id):
    note = get_or_404(Note, note_id)
    note.is_public = not note.is_public
    db.session.commit()
    return redirect(url_for('view_note', note_id=note.id))

# 分享

@app.route('/share/<int:note_id>')
def share_note(note_id):
    note = get_or_404(Note, note_id)
    if not note.is_public:
        return '这篇笔记不是公开的', 403
    safe_content = json.dumps(note.content)   # 防止 XSS 注入
    return f'''
    <h2>{note.title}</h2>
    <p>作者：{note.author.username}</p>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <div id="content"></div>
    <script>
        document.getElementById("content").innerHTML = marked.parse({safe_content});
    </script>
    '''

# 搜索

@app.route('/search')
@login_required
def search():
    query    = request.args.get('q', '').strip()
    scope    = request.args.get('scope', 'mine')
    folder_id = request.args.get('folder_id')
    tag_id    = request.args.get('tag_id')

    if scope == 'plaza':
        # 广场搜索直接重定向到广场页
        return redirect(url_for('plaza', q=query))

    q = Note.query.filter_by(user_id=current_user.id)
    if query:
        q = q.filter(Note.title.contains(query) | Note.content.contains(query))
    if folder_id:
        q = q.filter_by(folder_id=folder_id)
    if tag_id:
        tag = db.session.get(Tag, int(tag_id))
        if tag:
            q = q.filter(Note.tags.contains(tag))
    notes = q.order_by(Note.created_at.desc()).all()

    folders = Folder.query.filter_by(user_id=current_user.id).all()
    tags = (Tag.query
            .join(note_tags)
            .join(Note)
            .filter(Note.user_id == current_user.id)
            .distinct().all())

    return render_template('search.html', notes=notes, query=query,
                           scope=scope, folders=folders, tags=tags,
                           current_folder_id=int(folder_id) if folder_id else None,
                           current_tag_id=int(tag_id) if tag_id else None)

# 导入 / 导出

@app.route('/notes/import', methods=['POST'])
@login_required
def import_note():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.md'):
        return redirect(url_for('index'))
    filename = secure_filename(file.filename)
    title    = os.path.splitext(filename)[0]
    content  = file.read().decode('utf-8')
    note = Note(title=title, content=content, user_id=current_user.id)
    db.session.add(note)
    db.session.commit()
    return redirect(url_for('view_note', note_id=note.id))


@app.route('/notes/<int:note_id>/export')
@login_required
def export_note(note_id):
    note             = get_or_404(Note, note_id)
    encoded_filename = urllib.parse.quote(note.title + '.md')
    return Response(
        note.content,
        mimetype='text/markdown',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"},
    )

# 文件夹

@app.route('/folders/new', methods=['POST'])
@login_required
def new_folder():
    name = request.form.get('name', '').strip()
    if name:
        db.session.add(Folder(name=name, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/folders/<int:folder_id>/delete')
@login_required
def delete_folder(folder_id):
    folder = get_or_404(Folder, folder_id)
    for note in folder.notes:
        note.folder_id = None
    db.session.delete(folder)
    db.session.commit()
    return redirect(url_for('index'))

# 笔记广场

@app.route('/plaza')
@login_required
def plaza():
    q = request.args.get('q', '').strip()
    query = Note.query.filter_by(is_public=True)
    if q:
        query = query.filter(Note.title.contains(q) | Note.content.contains(q))
    notes = query.order_by(Note.created_at.desc()).all()
    return render_template('plaza.html', notes=notes, q=q)


@app.route('/plaza/<int:note_id>')
@login_required
def plaza_note(note_id):
    note = get_or_404(Note, note_id)
    if not note.is_public:
        from flask import abort
        abort(403)
    return render_template('plaza_note.html', note=note)


@app.route('/plaza/<int:note_id>/comment', methods=['POST'])
@login_required
def add_comment(note_id):
    note = get_or_404(Note, note_id)
    if not note.is_public:
        from flask import abort
        abort(403)
    content = request.form.get('content', '').strip()
    if content:
        comment = Comment(content=content, user_id=current_user.id, note_id=note.id)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('plaza_note', note_id=note.id))


@app.route('/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if not comment:
        from flask import abort
        abort(404)
    if comment.user_id != current_user.id:
        from flask import abort
        abort(403)
    note_id = comment.note_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('plaza_note', note_id=note_id))

# 启动 

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)