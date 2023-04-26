import datetime
import csv
from os import path
from flask import Flask, render_template, jsonify, redirect, request, make_response, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

import tubaerit_utils

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tubaerit.db'
app.config['SECRET_KEY'] = 'REPLACE'
ADMIN_PASSWORD = 'CHANGE'


bcrypt = Bcrypt()

db = SQLAlchemy(app)
app.app_context().push()

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    password = db.Column(db.String(64), nullable=False)
    createdTime = db.Column(db.DateTime(), default=datetime.datetime.now()) 

class Surveys(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    creator = db.Column(db.String(64), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    xName = db.Column(db.String(32))
    xMin = db.Column(db.Integer, nullable=False) 
    xMax = db.Column(db.Integer, nullable=False) 
    yName = db.Column(db.String(32), nullable=False)
    yMin = db.Column(db.Integer, nullable=False) 
    yMax = db.Column(db.Integer, nullable=False) 
    inputsLimit = db.Column(db.Integer, nullable=False, default=100_000) 
    createdTime = db.Column(db.DateTime(), default=datetime.datetime.now()) 
    

# Helper functions
def read_results(token):
    results = []
    with open(f'results/{token}.csv', newline='') as csvfile:
        resultsReader = csv.reader(csvfile, delimiter=' ')
        for result in resultsReader:
            results.append(result)
    return results

def count_answers(token):
    if not path.exists(f'results/{token}.csv'):
        return 0
    with open(f'results/{token}.csv') as file:
        return sum(1 for line in file)

def validate_login(name, password):
    accessedUser = Users.query.filter_by(name=name).first()
    if (bcrypt.check_password_hash(accessedUser.password, password)):
        return True
    return False

@app.route('/')
def start():
    return render_template('index.html')

@app.route('/survey/access/<token>', methods=['GET', 'POST'])
def serve_survey(token):
    accessedSurvey = Surveys.query.filter_by(token=token).first()

    if request.method == 'POST':
        # adding to inputs
        if (int(request.cookies.get(f'{token}_inputs')) >= accessedSurvey.inputsLimit):
            return render_template('fail.html')
        response = make_response(render_template('success.html'))
        currentCount = int(request.cookies.get(f'{token}_inputs'))
        response.set_cookie(f'{token}_inputs', str(currentCount+1))          
        # writing results into file
        with open(f'results/{token}.csv', 'a', newline='') as csvfile:
            resultsWriter = csv.writer(csvfile, delimiter=' ',)
            resultsWriter.writerow([request.form['xInput'],  request.form['yInput']])
        return response

    # getting data for page
    response = make_response(render_template('access_survey.html', title=accessedSurvey.title, xName=accessedSurvey.xName, xMin=accessedSurvey.xMin, xMax=accessedSurvey.xMax, yName=accessedSurvey.yName, yMin=accessedSurvey.yMin, yMax=accessedSurvey.yMax))
    # set cookie
    if (f'{token}_inputs' not in request.cookies):
        expireDate = datetime.datetime.now()
        expireDate += datetime.timedelta(days=7)
        response.set_cookie(f'{token}_inputs', '0', expires=expireDate)
    return response
        

@app.route('/survey/create', methods=['GET', 'POST'])
def create_survey():
    if request.method == 'POST':
        if (session.get('username')):
            # collecting data
            creator = session['username']
            token = tubaerit_utils.generateToken(8)
            while (Surveys.query.filter_by(token=token).first()):
                token = tubaerit_utils.generateToken(8) # making sure the token isnt already used
            xMin = None
            xMax = None
            yMin = None
            yMax = None
            if (request.form['xMin']):
                xMin = request.form['xMin']
            if (request.form['xMax']):
                xMax = request.form['xMax']
            if (request.form['yMin']):
                yMin = request.form['yMin']
            if (request.form['xMax']):
                yMax = request.form['yMax']

            # making database entry
            newSurvey = Surveys(title=request.form['title'], creator=creator, token=token, xName=request.form['xName'], xMin=xMin, xMax=xMax, yName=request.form['yName'], yMin=yMin, yMax=yMax, inputsLimit=request.form['inputsLimit'])
            db.session.add(newSurvey)
            db.session.commit()
            db.session.refresh(newSurvey)     
            return render_template('survey_created.html', token=token) 
        return redirect('/user/login')
    return render_template('create_survey.html')

@app.route('/survey/results/<token>', methods=['GET', 'POST'])
def show_results(token):    
    # getting information about the survey
    accessedSurvey = Surveys.query.filter_by(token=token).first()
    # getting results
    gatheredData = read_results(token)
    return render_template('results_survey.html', title=accessedSurvey.title, xName=accessedSurvey.xName, xMin=accessedSurvey.xMin, xMax=accessedSurvey.xMax, yName=accessedSurvey.yName, yMin=accessedSurvey.yMin, yMax=accessedSurvey.yMax, data=jsonify(gatheredData), token=token)

@app.route('/user/surveys')
def all_surveys():
    #getting all surveys
    surveyEntrys = Surveys.query.all()
    surveys = []
    for surveyEntry in surveyEntrys:
        survey = {}
        survey['title'] = surveyEntry.title
        survey['answerCount'] = count_answers(surveyEntry.token)
        survey['token'] = surveyEntry.token
        surveys.append(survey)
    print(surveys)
    return render_template('manage_surveys.html', surveys=surveys)

@app.route('/update/<token>', methods=['GET'])
def update_results(token):
    gatheredData = read_results(token)
    print(gatheredData)
    data = jsonify(gatheredData)
    print(data)
    # Return data as JSON response
    return data

@app.route('/user/login', methods=['GET', 'POST'])
def login_user():
    if (request.method=='POST'):
        valid = validate_login(request.form['username'], request.form['userPassword'])
        if valid:
            session['username'] = request.form['username']
            return render_template('success.html')
        return render_template('fail.html')
    return render_template('user_login.html')

@app.route('/user/create', methods=['GET', 'POST'])
def create_user():
    if (request.method=='POST'):
        if (request.form['adminPassword'] == ADMIN_PASSWORD):
            newUser = Users(name=request.form['username'], password=bcrypt.generate_password_hash(request.form['userPassword']))
            db.session.add(newUser)
            db.session.commit()
            db.session.refresh(newUser)   
            return render_template('success.html')
        return render_template('fail.html')
    return render_template('user_create.html')