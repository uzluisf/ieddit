from flask import Flask, render_template, session, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, exists

from werkzeug.security import generate_password_hash, check_password_hash
import re
import config

from models import *
from functions import *

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)

@app.route('/')
def index():
	return subi('all')
	
@app.route('/login',  methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return render_template('login.html')
	if request.method == 'POST':
		username = request.form.get('username')
		password = request.form.get('password')
		if username == None or password == None:
			flash('Username or Password missing.', 'error')
			return redirect(url_for('login'), 302)
		if username == '' or password == '' or len(username) > 20 or len(password) > 100:
			flash('Username or Password empty.', 'error')
			return redirect(url_for('login'), 302)

		if db.session.query(db.session.query(Iuser)
				.filter_by(username=username)
				.exists()).scalar():
			login_user = db.session.query(Iuser).filter_by(username=username).first()
			hashed_pw = login_user.password
			if check_password_hash(hashed_pw, password):
				[session.pop(key) for key in list(session.keys())]
				session['username'] = login_user.username
				session['user_id'] = login_user.id
				return redirect(url_for('index'), 302)

		flash('Username or Password incorrect.', 'error')
		return redirect(url_for('login'), 302)

@app.route('/register', methods=['POST'])
def register():
	if request.method == 'POST':
		username = request.form.get('username')
		password = request.form.get('password')
		email = request.form.get('email')

		if username == None or password == None:
			flash('username or password missing', 'error')
			return redirect(url_for('login'))

		if verify_username(username):
			if db.session.query(db.session.query(Iuser).filter(func.lower(Iuser.username) == func.lower(username)).exists()).scalar():
				flash('username exists', 'error')
				return redirect(url_for('login'))
		else:
			flash('invalid username', 'error')
			return redirect(url_for('login'))

		if len(password) > 100:
			flash('password too long', 'error')
			return redirect(url_for('login'))

		if email != None and email != '':
			if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
				flash('invalid email', 'error')
				return redirect(url_for('login'))

		new_user = Iuser(username=username, email=email,
			password=generate_password_hash(password))
		db.session.add(new_user)
		db.session.commit()
		session['username'] = new_user.username
		session['user_id'] = new_user.id
		return redirect(config.URL, 302)

# These two functions look the same, but they will work somewhat different in fucture
@app.route('/r/<subi>/')
def subi(subi, user_id=None, posts_only=False):
	if subi != 'all':
		if verify_subname(subi) == False:
			flash('invalid subname', 'error')
			return urlfor('index')
		subname = db.session.query(Sub).filter(func.lower(Sub.name) == subi.lower()).first()

		if subname == None:
			flash('no subname', 'error')
			return urlfor('index')
		posts = db.session.query(Post).filter_by(sub=subi).all()
	elif user_id != None:
		posts = db.session.query(Post).filter_by(author_id=user_id).all()
	else:
		posts = db.session.query(Post).all()
	p = []
	for post in posts:
		post.created_ago = time_ago(post.created)
		if subi != 'all':
			post.site_url = config.URL + '/r/' + subi + '/' + str(post.id) + '/' + post.inurl_title
		post.remote_url_parsed = post_url_parse(post.url)
		post.comment_count = db.session.query(Comment).filter_by(post_id=post.id).count()
		if 'user_id' in session:
			post.has_voted = db.session.query(Vote).filter_by(post_id=post.id, user_id=session['user_id']).first()
			if post.has_voted != None:
				post.has_voted = post.has_voted.vote
		p.append(post)

	if posts_only:
		return p
	return render_template('sub.html', posts=p, url=config.URL)

@app.route('/r/<sub>/<post_id>/<inurl_title>/<comment_id>/sort-<sort_by>')
@app.route('/r/<sub>/<post_id>/<inurl_title>/<comment_id>/')
@app.route('/r/<sub>/<post_id>/<inurl_title>/sort-<sort_by>')
@app.route('/r/<sub>/<post_id>/<inurl_title>/')
def get_comments(sub=None, post_id=None, inurl_title=None, comment_id=False, sort_by=None, comments_only=False, user_id=None):
	if sub == None or post_id == None or inurl_title == None:
		if not comments_only:
			return 'badlink'
	try:
		int(comment_id)
	except:
		comment_id = False

	if not comments_only:
		post = db.session.query(Post).filter_by(id=post_id, sub=sub).first()
		post.comment_count = db.session.query(Comment).filter_by(post_id=post.id).count()
		post.created_ago = time_ago(post.created)
		post.remote_url_parsed = post_url_parse(post.url)
	
		if 'user_id' in session:
			post.has_voted = db.session.query(Vote).filter_by(post_id=post.id, user_id=session['user_id']).first()
			if post.has_voted != None:
				post.has_voted = post.has_voted.vote
	
		if not comment_id:
			if sort_by == 'new':
				comments = db.session.query(Comment).filter(Comment.post_id == post_id, Comment.level < 7)\
				.order_by((Comment.created).asc()).all()
			else:
				comments = db.session.query(Comment).filter(Comment.post_id == post_id, Comment.level < 7)\
				.order_by((Comment.ups - Comment.downs).desc()).all()
	
			parent_comment = None
			parent_posturl = None
		else:
			comments = list_of_child_comments(comment_id, sort_by=sort_by)
			parent_comment = db.session.query(Comment).filter_by(id=comment_id).first()
			comments.append(parent_comment)
	else:
		comments = db.session.query(Comment).filter(Comment.author_id == user_id).order_by(Comment.created.desc()).all()

	for c in comments:
		c.created_ago = time_ago(c.created)
		if 'user_id' in session:
			c.has_voted = db.session.query(Vote).filter_by(comment_id=c.id, user_id=session['user_id']).first()
			if c.has_voted != None:
				c.has_voted = c.has_voted.vote

	if comments_only:
		return comments

	if not comment_id:
		tree = create_id_tree(comments)
	else:
		tree = create_id_tree(comments, parent_id=comment_id)

	tree = comment_structure(comments, tree)
	return render_template('comments.html', comments=comments, post_id=post_id, 
		post_url='%s/r/%s/%s/%s/' % (config.URL, sub, post_id, post.inurl_title), 
		post=post, tree=tree, parent_comment=parent_comment)

# need to entirely rewrite how comments are handled once everything else is complete
# this sort of recursion KILLS performance, especially when combined with the already
# terrible comment_structure function. only reason i'm doing it this way now is
# performance doens't matter and i don't have redis/similar setup yet
def list_of_child_comments(comment_id, sort_by=None):
	comments = {}
	current_comments = []
	if sort_by == 'new':
		start = db.session.query(Comment).filter(Comment.parent_id == comment_id)\
					.order_by((Comment.created).asc()).all()
	else:
		start = db.session.query(Comment).filter(Comment.parent_id == comment_id)\
					.order_by((Comment.ups - Comment.downs).desc()).all()

	for c in start:
		current_comments.append(c.id)
		comments[c.id] = c
	while len(current_comments) > 0:
		for current_c in current_comments:
			if sort_by == 'new':
				get_comments = db.session.query(Comment).filter(Comment.parent_id == current_c)\
					.order_by((Comment.created).asc()).all()
			else:
				get_comments = db.session.query(Comment).filter(Comment.parent_id == current_c)\
					.order_by((Comment.ups - Comment.downs).desc()).all()
			for c in get_comments:
				current_comments.append(c.id)
				comments[c.id] = c
			current_comments.remove(current_c)
	return [comments[c] for c in comments]

@app.route('/create', methods=['POST', 'GET'])
def create_sub():
	if request.method == 'POST':
		subname = request.form.get('subname')
		if subname != None and verify_subname(subname) and 'username' in session:
			if len(subname) > 30 or len(subname) < 1:
				return 'invalid length'
			new_sub = Sub(name=subname, created_by=session['username'])
			db.session.add(new_sub)
			db.session.commit()
			return redirect(config.URL + '/r/' + subname, 302)
		return 'invalid'
	elif request.method == 'GET':
		return render_template('create.html')

@app.route('/u/<username>/', methods=['GET'])
def view_user(username):
	vuser = db.session.query(Iuser).filter_by(username=username).first()
	mod_of = db.session.query(Moderator).filter_by(user_id=vuser.id).all()
	mods = {}
	for s in mod_of:
		mods[s.sub_name] = s.rank
	vuser.mods = str(mods)
	posts = subi('all', user_id=vuser.id, posts_only=True)
	#sub, post_id, inurl_title, comment_id=False, sort_by=None, comments_only=False, user_id=None):
	comments_with_posts = []
	comments = get_comments(comments_only=True, user_id=vuser.id)
	for c in comments:
		cpost = db.session.query(Post).filter_by(id=c.post_id).first()
		comments_with_posts.append((c, cpost))
	return render_template('user.html', vuser=vuser, posts=posts, url=config.URL, comments_with_posts=comments_with_posts)

@app.route('/vote', methods=['GET', 'POST'])
def vote():
	if request.method == 'POST':
		post_id = request.form.get('post_id')
		comment_id = request.form.get('comment_id')
		vote = request.form.get('vote')
	
		if 'username' not in session or 'user_id' not in session:
			return 'not logged in'
		else:
			user_id = session['user_id']
			username = session['username']
		if comment_id != None and post_id != None:
			return 'cannot vote for 2 objects'
		if comment_id == None and post_id == None:
			return 'no vote object'
		if vote not in ['1', '-1', '0']:
			return 'invalid vote amount'
	
		vote = int(vote)

		invert_vote = False
		if post_id != None:
			last_vote = db.session.query(Vote).filter_by(user_id=user_id, post_id=post_id).first()
			if last_vote != None:
				if last_vote.vote == vote:
					return 'already voted'
				else:
					invert_vote = True

		elif comment_id != None:
			last_vote = db.session.query(Vote).filter_by(user_id=user_id, comment_id=comment_id).first()
			if last_vote != None:
				if last_vote.vote == vote:
					return 'already voted'
				else:
					invert_vote = True

		if vote == 0 and last_vote == None:
			return 'never voted'

		if vote == 0:
			if last_vote.post_id != None:
				if last_vote.post_id != None:
					vpost = db.session.query(Post).filter_by(id=last_vote.post_id).first()
				elif last_vote.comment_id != None:
					vpost = db.session.query(Comment).filter_by(id=last_vote.post_id).first()
				if last_vote.vote == 1:
					vpost.ups -= 1
				elif last_vote.vote == -1:
					vpost.downs -= 1
			db.session.delete(last_vote)
			db.session.commit()
			return str(vpost.ups - vpost.downs)

		if last_vote == None:
			new_vote = Vote(user_id=user_id, vote=vote, comment_id=comment_id, post_id=post_id)
			db.session.add(new_vote)
			db.session.commit()

		elif invert_vote:
			if last_vote.vote == 1:
				last_vote.vote = -1
			else:
				last_vote.vote = 1
		db.session.commit()

		if comment_id != None:
			vcom = db.session.query(Comment).filter_by(id=comment_id).first()
		elif post_id != None:
			vcom = db.session.query(Post).filter_by(id=post_id).first()


		if vote == 1:
			if not invert_vote:
				vcom.ups += 1
			else:
				vcom.ups += 1
				vcom.downs -= 1

		elif vote == -1:
			if not invert_vote:
				vcom.downs += 1
			else:
				vcom.downs += 1
				vcom.ups -= 1

		db.session.commit()	

	
		return str(vcom.ups - vcom.downs)
	elif request.method == 'GET':
		return 'get'

@app.route('/create_post', methods=['POST', 'GET'])
def create_post():
	if request.method == 'POST':
		title = request.form.get('title')
		url = request.form.get('url')
		sub = request.form.get('sub')
		self_post_text = request.form.get('self_post_text')

		if self_post_text != None:
			post_type = 'self_post'
		elif url != None:
			post_type = 'url'
		else:
			flash('invalid post type, not url or self', 'error')
			return redirect(url_for('create_post'))

		if title == None or 'username' not in session or 'user_id' not in session:
			flash('invalid post, no title/username/uid', 'error')
			return redirect(url_for('create_post'))
		if len(title) > 400 or len(title) < 1 or len(sub) > 30 or len(sub) < 1:
			flash('invalid title/sub length', 'error', 'error')
			return redirect(url_for('create_post'))

		if post_type == 'url':
			if len(url) > 2000 or len(url) < 1:
				flash('invalid url length', 'error')
				return redirect(url_for('create_post'))
			new_post = Post(url=url, title=title, inurl_title=convert_ied(title), author=session['username'], author_id=session['user_id'], sub=sub, post_type=post_type)
		elif post_type == 'self_post':
			if len(self_post_text) < 1 or len(self_post_text) > 20000:
				flash('invalid self post length', 'error')
				return redirect(url_for('create_post'))
			new_post = Post(self_text=self_post_text, title=title, inurl_title=convert_ied(title), author=session['username'], author_id=session['user_id'], sub=sub, post_type=post_type)

		db.session.add(new_post)
		db.session.commit()
		url = config.URL + '/r/' + sub
		return redirect(url, 302)

	if request.method == 'GET':
		return render_template('create_post.html')

@app.route('/create_comment', methods=['POST'])
def create_comment():
	text = request.form.get('comment_text')
	post_id = request.form.get('post_id')
	post_url = request.form.get('post_url')
	parent_id = request.form.get('parent_id')
	sub_name = request.form.get('sub_name')

	if parent_id == '':
		parent_id = None

	if post_url != None:
		if post_url_parse(post_url) != post_url_parse(config.URL):
			flash('bad origin url', 'error')
			return redirect('/')

	if 'username' not in session:
		flash('not logged in', 'error')
		return redirect(post_url)

	elif text == None or post_id == None or sub_name == None:
		flash('bad comment', 'error')
		return redirect(post_url)

	if parent_id != None:
		level = (db.session.query(Comment).filter_by(id=parent_id).first().level) + 1
	else:
		level = None
	new_comment = Comment(post_id=post_id, sub_name = sub_name, text=text, author=session['username'], author_id=session['user_id'], parent_id=parent_id, level=level)
	db.session.add(new_comment)
	db.session.commit()
	return redirect(post_url, 302)

@app.route('/logout', methods=['POST', 'GET'])
def logout():
	[session.pop(key) for key in list(session.keys())]
	return redirect(url_for('index'), 302)