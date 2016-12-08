from flask import Flask, session, flash, render_template, request, jsonify, url_for, redirect, g
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, case, desc
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from math import log, sqrt
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = "insecure"
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:pass@localhost/sgbgc'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

cats = ["Early Earth and Global BGC", "Humans and BGC", "Thermodynamics", "Elemental Cycles", "Energetics",
    "Trophic Interactions", "Redox Chemistry", "Stoichiometry", "Methodology", "History of BGC"]
cats = {x.replace(" ","+"):x for x in cats}

########## DATABASE
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class Articles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    indate = db.Column(db.DateTime)
    td = db.Column(db.Integer)
    by = db.Column(db.Integer)
    title = db.Column(db.Text)
    year = db.Column(db.Integer)
    author = db.Column(db.Text)
    source = db.Column(db.Text)
    link = db.Column(db.Text)
    doi = db.Column(db.Text)
    category = db.Column(db.Text)
    subcategory = db.Column(db.Text)
    keywords = db.Column(db.Text)
    upvotes = db.Column(db.Integer)
    downvotes = db.Column(db.Integer)
    def __init__(self, indate, td, by, title, year, author, source, link, doi, category, subcategory, keywords, upvotes, downvotes):
        self.indate = indate
	self.td = td
        self.by = by
        self.title = title
        self.year = year
        self.author = author
        self.source = source
        self.link = link
        self.doi = doi
        self.category = category
        self.subcategory = subcategory
        self.keywords = keywords
        self.upvotes = upvotes
        self.downvotes = downvotes
    def __repr__(self):
        return '<Article %r>' % self.title
    @hybrid_property
    def best(self):
	n = self.upvotes + self.downvotes
	if n == 0:
            return 0
        z = 1.281551565545
        p = float(self.upvotes) / n
        left = p + z*z/(2*n)
        right = z*sqrt(p*(1-p)/n + z*z/(4*n*n))
        under = 1+z*z/n
        return 100*(left-right)/under
    @best.expression
    def best(cls):
        n = cls.upvotes + cls.downvotes
        z = 1.281551565545
        p = cls.upvotes*1.0 / n
        left = p + z*z/(2*n)
        right = z*func.sqrt(p*(1-p)/n + z*z/(4*n*n))
        under = 1+z*z/n
        return func.IF(n==0, 0, 100*(left-right)/under)
    @hybrid_property
    def hot(self):
        ts = self.td*1. - 1449619200 # seconds since 2015-12-09
        x = self.upvotes-self.downvotes
        o = log(max(abs(x), 1))
        y = 1 if x>0 else -1 if x<0 else 0
        return o*y+ts/300000
    @hot.expression
    def hot(cls):
        ts = cls.td - 1449619200
        x = cls.upvotes - cls.downvotes
        o = func.log(func.IF(func.abs(x)>1, func.abs(x), 1))
        y = func.IF(x>0, 1, func.IF(x<0, -1, 0))
        return o*y+ts*1.0/300000

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(55), unique=True, index=True)
    password = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    registered_on = db.Column(db.DateTime())
    def __init__(self, username, password, email):
        self.username = username
        self.set_password(password)
        self.email = email
        self.registered_on = datetime.utcnow()
    def set_password(self, password):
        self.password = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password, password)
    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return unicode(self.id)
    def __repr__(self):
        return '<User %r>' % self.username

class Votes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    user = db.Column(db.Integer)
    post = db.Column(db.Integer)
    voteup = db.Column(db.Boolean)
    def __init__(self, date, user, post, voteup):
        self.date = date
        self.user = user
        self.post = post
        self.voteup = voteup
    def __repr__(self):
        return '<PostBy %r>' % self.user

db.create_all()

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.before_request
def before_request():
    g.user = current_user

########## FUNCTIONS
def crossref(s):
    out = []
    sq = s.replace(" ", "+")
    url = 'http://api.crossref.org/works?query='+sq
    r = requests.get(url)
    res = r.json()['message']['items']
    res = [x for x in res if 'DOI' in x] # only things with a DOI
    for x in res:
        doi = x['DOI']
        if 'author' in x:
            autlist = [a['family']+', '+''.join([i[0] for i in a['given'].split()]) if 'given' in a and 'family' in a else '' for a in x['author']]
            author = "; ".join(autlist)
        else:
            author = ''
        link = x['URL'] if 'URL' in x else ''
        title = x['title'][0] if len(x['title'])>0 else ''
        source = x['container-title'][0] if len(x['container-title'])>0 else ''
        year = str(x['issued']['date-parts'][0][0]) if 'issued' in x else ''
        out.append({'title':title,'authors':author,'source':source,'link':link,'doi':doi,'year':year})
    return out

def keys(k):
    return [x.strip() for x in k.split(",")]

def getarticles(page,c=None,s=None,k=None,sort='best'):
    nper = 20
    q = Articles.query
    if c is not None:
        q = q.filter_by(category=c)
    if s is not None:
        q = q.filter_by(subcategory=s)
    if k is not None:
        q = q.filter(Articles.keywords.op('regexp')(k))
    a = []
    if sort=='best':
        pages = q.order_by(Articles.best.desc()).paginate(page,nper,False)
        for x in pages.items:
            a.append({'id':x.id,
                'indate':x.indate.strftime('%Y-%m-%d %H:%M:%S'),
                'by':User.query.filter_by(id=x.by).first().username,
                'title':x.title,
                'year':x.year,
                'author':x.author,
                'source':x.source,
                'link':x.link,
                'doi':x.doi,
                'category':x.category,
                'subcategory':x.subcategory,
                'keywords':keys(x.keywords),
                'sort':x.best})
    else:
        pages = q.order_by(Articles.hot.desc()).paginate(page,nper,False)
        for x in pages.items:
            a.append({'id':x.id,
                'indate':x.indate.strftime('%Y-%m-%d %H:%M:%S'),
                'by':User.query.filter_by(id=x.by).first().username,
                'title':x.title,
                'year':x.year,
                'author':x.author,
                'source':x.source,
                'link':x.link,
                'doi':x.doi,
                'category':x.category,
                'subcategory':x.subcategory,
                'keywords':keys(x.keywords),
                'sort':x.hot})
    meta = {'has_prev':pages.has_prev,'has_next':pages.has_next,
        'prev_num':pages.prev_num,'next_num':pages.next_num,
        'page':pages.page,'total':pages.total,'nper':nper}
    return {'asort':a, 'meta':meta}

# newart = Articles(indate=datetime.utcnow(),
#     by=1,
#     title="fake",
#     author="Aaron Berdanier",
#     year=0,
#     source="Src",
#     link="",
#     doi="102/23.2",
#     category="",
#     subcategory="",
#     keywords="",
#     upvotes=0, downvotes=0)
# db.session.add(newart)
# db.session.commit()
# user = User('berdaniera','Xpbrec1!','aaron.berdanier@gmail.com')
# db.session.add(user)
# db.session.commit()
#
########## PAGES
@app.route('/')
@app.route('/index')
@app.route('/index/<int:page>')
def index(page=1,sort='best'):
    if request.args.get('sort') is not None:
	sort = request.args.get('sort')
    adata = getarticles(page,sort=sort)
    asort = adata['asort']
    meta = adata['meta']
    return render_template('index.html', articles=asort, meta=meta, cat=None, subcat=None, keyw=None, categories=cats, sortdisp=sort)

@app.route('/register' , methods=['GET','POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html', categories=cats, cat=None)
    # eml = re.compile('.*@.*\.edu')
    # if not eml.match(request.form['email']):
    #     flash('Please use a ')
    # if not Swot.is_academic(request.form['email']):
    #     flash('Please register with an official academic email address.', 'alert-danger')
    #     return redirect(url_for('register'))
    user = User(request.form['username'], request.form['password'], request.form['email'])
    db.session.add(user)
    db.session.commit()
    flash('User successfully registered', 'alert-success')
    return redirect(url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', categories=cats, cat=None)
    username = request.form['username']
    password = request.form['password']
    registered_user = User.query.filter_by(username=username).first()
    if registered_user is None:
        flash('Username is invalid' , 'alert-danger')
        return redirect(url_for('login'))
    if not registered_user.check_password(password):
        flash('Password is invalid', 'alert-danger')
        return redirect(url_for('login'))
    login_user(registered_user)
    flash('Logged in successfully', 'alert-success')
    return redirect(request.args.get('next') or url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/_upvote', methods=['POST'])
def upit():
    ux = current_user.get_id()
    ax = request.json['id']
    if Votes.query.filter_by(user=ux).filter_by(post=ax).first() is None:
        a = Articles.query.filter_by(id=ax).first()
        a.upvotes += 1
        db.session.commit()
        v = Votes(datetime.utcnow(), int(ux), int(ax), True)
        db.session.add(v)
        db.session.commit()
        return jsonify(result="Success")
    else:
        return jsonify(result="Fail")

@app.route('/_downvote', methods=['POST'])
def down():
    ux = current_user.get_id()
    ax = request.json['id']
    if Votes.query.filter_by(user=ux).filter_by(post=ax).first() is None:
        a = Articles.query.filter_by(id=ax).first()
        a.downvotes += 1
        db.session.commit()
        v = Votes(datetime.utcnow(), int(ux), int(ax), False)
        db.session.add(v)
        db.session.commit()
        return jsonify(result="Success")
    else:
        return jsonify(result="Fail")

@app.route('/add')
@login_required
def add():
    return render_template('add.html', categories=cats, cat=None)

@app.route('/_query', methods=['POST'])
def scholar():
    st = request.json['s']
    result = crossref(st)
    return jsonify(result=result)

@app.route('/_confirm', methods=['POST'])
def add_confirm():
    art = request.json
    if Articles.query.filter_by(doi=art['doi']).first() is None:
	dtn = datetime.utcnow()
        newart = Articles(indate=dtn,
	    td=int((dtn-datetime(1970,1,1)).total_seconds()),
            by=current_user.get_id(),
            title=art['title'],
            author=art['authors'],
            year=int(art['year']),
            source=art['source'],
            link=art['link'],
            doi=art['doi'],
            category=art['category'],
            subcategory=art['subcategory'],
            keywords=art['keywords'],
            upvotes=0, downvotes=0)
        db.session.add(newart)
        db.session.commit()
	return jsonify(result="Added successfully!",status="success")
    else:
        return jsonify(result="Already in the database!",status="warning")

@app.route('/c/<category>',defaults={'subcategory':None})
@app.route('/c/<category>/<int:page>',defaults={'subcategory':None})
@app.route('/c/<category>/<subcategory>')
@app.route('/c/<category>/<subcategory>/<int:page>')
def show_content(category, subcategory, page=1,sort='best'):
    category = category#.replace("+"," ")
    if subcategory is not None:
        subcategory = subcategory.replace("+"," ")
    if request.args.get('sort') is not None:
	sort=request.args.get('sort')
    adata = getarticles(page,c=category,s=subcategory,sort=sort)
    asort = adata['asort']
    meta = adata['meta']
    if len(asort)==0:
        flash('No results found, please try again.', 'alert-danger')
        return redirect(url_for('index'))
    return render_template('index.html', articles=asort, meta=meta, cat=category, subcat=subcategory, keyw=None, categories=cats,sortdisp=sort)

@app.route('/search', methods=['GET'])
@app.route('/search/<int:page>', methods=['GET'])
def search(page=1,sort='best'):
    if request.args.get('sort') is not None:
	sort = request.args.get('sort')
    keyword = request.args['k']
    adata = getarticles(page,k=keyword,sort=sort)
    asort = adata['asort']
    meta = adata['meta']
    if len(asort)==0:
        flash('No results found, please try again.', 'alert-danger')
        return redirect(url_for('index'))
    return render_template('index.html', articles=asort, meta=meta, cat=None, subcat=None, keyw=keyword, categories=cats,sortdisp=sort)

#### RUN
if __name__ == '__main__':
    app.run(host='0.0.0.0')
