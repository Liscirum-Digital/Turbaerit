import os
import datetime
import csv
import random
from os import path, getcwd
from flask import Flask, render_template, jsonify, redirect, request, make_response, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

import tubaerit_utils

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tubaerit.db'
app.config['SECRET_KEY'] = 'REPLACE'
ADMIN_NAME = 'EDIT'
ADMIN_PASSWORD = 'CHANGE'

os.chdir(os.path.dirname(os.path.abspath(__file__)))

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
    inputsLimit = db.Column(db.Integer, nullable=False)
    createdTime = db.Column(db.DateTime(), default=datetime.datetime.now()) 
    

# Helper functions
def sort_array(arr):
    arr.sort(key=lambda x: float(x[0]))
    return arr

def read_results(token):
    results = []
    with open(f'results/{token}.csv', newline='') as csvfile:
        resultsReader = csv.reader(csvfile, delimiter=',')
        for result in resultsReader:
            results.append(result)
    return sort_array(results)

def count_answers(token):
    if not path.exists(f'results/{token}.csv'):
        return 0
    with open(f'results/{token}.csv') as file:
        return sum(1 for line in file)

def validate_login(name, password):
    accessedUser = Users.query.filter_by(name=name).first()
    if (accessedUser and bcrypt.check_password_hash(accessedUser.password, password)):
        return True
    return False

@app.route('/')
def start():
    logo_index = 1
    if (random.randint(1,200)==1):
        logo_index=2
    return render_template('index.html', user=session.get('username'), admin=session.get('admin'), logo_index=logo_index)

@app.route('/survey/access/<token>', methods=['GET', 'POST'])
def serve_survey(token):
    accessedSurvey = Surveys.query.filter_by(token=token).first()

    if request.method == 'POST':
        # adding to inputs
        if (session.get(f'{token}_inputs') >= accessedSurvey.inputsLimit):
            return render_template('access_survey.html', errorCode='overLimit', survey=accessedSurvey, user=session.get('username'), admin=session.get('admin'))
        session[f'{token}_inputs']+=1
        # writing results into file
        with open(f'results/{token}.csv', 'a', newline='') as csvfile:
            resultsWriter = csv.writer(csvfile, delimiter=',')
            resultsWriter.writerow([request.form['xInput'],  request.form['yInput']])
        return render_template('success.html', token=token, topic='newResult', user=session.get('username'), admin=session.get('admin'))

    # getting data for page
    # set cookie
    if (not session.get(f'{token}_inputs')):
        session.permanent = True
        session[f'{token}_inputs']=0
    return render_template('access_survey.html', survey=accessedSurvey, user=session.get('username'), admin=session.get('admin'))
        

@app.route('/survey/new', methods=['GET', 'POST'])
def create_survey():
    if request.method == 'GET':
        return render_template('create_survey.html', user=session.get('username'), admin=session.get('admin'))
    if (not session.get('username')):
        return redirect('/user/login')
    # collecting data
    token = tubaerit_utils.generateToken(8)
    while (Surveys.query.filter_by(token=token).first()):
        token = tubaerit_utils.generateToken(8) # making sure the token isnt already used
    
    iLimit = 2_147_483_647
    if (request.form['inputsLimit']):
        iLimit=request.form['inputsLimit']

    # making database entry
    newSurvey = Surveys(
        title=request.form['title'], 
        creator=session.get('username'), 
        token=token, 
        xName=request.form['xName'], 
        xMin=request.form['xMin'], 
        xMax=request.form['xMax'], 
        yName=request.form['yName'], 
        yMin=request.form['yMin'], 
        yMax=request.form['yMax'], 
        inputsLimit=iLimit)
    db.session.add(newSurvey)
    db.session.commit()
    db.session.refresh(newSurvey)     
    open(f'results/{token}.csv', 'x') 
    return render_template('success.html', token=token, topic='newSurvey', user=session.get('username'), admin=session.get('admin')) 

@app.route('/survey/edit/<token>', methods=['GET', 'POST'])
def edit_survey(token):
    accessedSurvey = Surveys.query.filter_by(token=token).first()
    if (accessedSurvey.creator != session.get('username')):
        return redirect('/user/login', errorCode='wrong-account')
    if request.method == 'GET':
        return render_template('edit_survey.html', survey=accessedSurvey, user=session.get('username'), admin=session.get('admin'))

    #making database entry
    accessedSurvey.title=request.form['title']
    accessedSurvey.xName=request.form['xName']
    accessedSurvey.xMin=request.form['xMin']
    accessedSurvey.xMax=request.form['xMax']
    accessedSurvey.yName=request.form['yName']
    accessedSurvey.yMin=request.form['yMin']
    accessedSurvey.yMax=request.form['yMax']
    accessedSurvey.inputsLimit = 2_147_483_647
    if (request.form['inputsLimit']):
        accessedSurvey.inputsLimit=request.form['inputsLimit']
    db.session.commit()  
    return render_template('success.html', token=token, topic='editSurvey', user=session.get('username'), admin=session.get('admin')) 
    
    

@app.route('/survey/results/<token>', methods=['GET', 'POST'])
def show_results(token):    
    # getting information about the survey
    accessedSurvey = Surveys.query.filter_by(token=token).first()
    # getting results
    gatheredData = read_results(token)
    return render_template(
        'results_survey.html',
        survey=accessedSurvey, 
        data=jsonify(gatheredData),
        username=session.get('username'),
        creator = session.get('username') == accessedSurvey.creator)

@app.route('/survey/delete/<token>', methods=['GET', 'POST'])
def delete_survey(token):
    accessedSurvey = Surveys.query.filter_by(token=token).first()
    if (session.get('username') != accessedSurvey.creator): # wrong user
        return redirect('/user/login', errorCode='wrong-account')
    if (request.method == 'GET'):
        return render_template('delete_survey.html', survey=accessedSurvey, admin=session.get('admin'))
    # Delete survey
    print(f'results/${token}.csv')
    if os.path.exists(f'results/{token}.csv'):
        os.remove(f'results/{token}.csv')
    Surveys.query.filter_by(token=token).delete()
    db.session.commit()

    return redirect('/user/surveys')

@app.route('/survey/download/<token>', methods=['GET', 'POST'])
def download_results(token):    
    if request.method == 'POST':
        uploads = path.join(getcwd(), 'results')
        return send_from_directory(uploads, f'{token}.csv')
    accessedSurvey = Surveys.query.filter_by(token=token).first()
    return render_template('download_results.html', title=accessedSurvey.title, user=session.get('username'), admin=session.get('admin'))

@app.route('/survey/delete-point/<token>', methods=['GET', 'POST'])
def delete_point(token):
    if (request.method == 'GET'):
        return redirect('/')
    if (session.get('username') != Surveys.query.filter_by(token=token).first().creator): # wrong user
        return redirect('/user/login', errorCode='wrong-account')
    deleteX = request.form.get('deleteX')
    deleteY = request.form.get('deleteY')
    deletePoint = [deleteX, deleteY]
    print(deletePoint)
    oldData = read_results(token)
    with open(f'results/{token}.csv', 'w', newline='') as newFile:
        writer = csv.writer(newFile, delimiter=',')
        for line in oldData:
            print(line)
            if line!=deletePoint:
                writer.writerow(line)
    return redirect(f'/survey/results/{token}')

@app.route('/user/surveys')
def all_surveys():
    if (not session.get('username')):
        return redirect('/user/login')
    
    #getting all surveys
    surveyEntrys = Surveys.query.filter_by(creator=session.get('username')).all()
    surveys = []
    for surveyEntry in surveyEntrys:
        survey = {}
        survey['title'] = surveyEntry.title
        survey['answerCount'] = count_answers(surveyEntry.token)
        survey['token'] = surveyEntry.token
        surveys.append(survey)
    return render_template('manage_surveys.html', surveys=surveys, admin=session.get('admin'))

@app.route('/update/<token>', methods=['GET'])
def update_results(token):
    gatheredData = read_results(token)
    data = jsonify(gatheredData)
    return data

@app.route('/user/login', methods=['GET', 'POST'])
def login_user():
    if (session.get('username')):
        return redirect('/user/logout')
    if (request.method=='GET'):
        return render_template('user_login.html')
    valid = validate_login(request.form['username'], request.form['userPassword'])
    if not valid:
        return render_template('user_login.html', errorCode='wrong-credentials')
    session.permanent = True
    session['username'] = request.form['username']
    return render_template('success.html', topic='login', user=session.get('username'), admin=session.get('admin'))
   
@app.route('/user/logout', methods=['GET', 'POST'])
def logout_user():
    if (not session.get('username')):
        return redirect('/user/login')
    if (request.method=='GET'):
        return render_template('user_logout.html', user=session.get('username'), admin=session.get('admin'))
    session.pop('username')
    if session.get('admin'):
        session.pop('admin')
    return render_template('success.html', topic='logout', user=session.get('username'), admin=session.get('admin'))
    
@app.route('/user/new', methods=['GET', 'POST'])
def create_user():
    if (not session.get('admin')):
        return redirect('/admin/login')
    if (request.method=='GET'):
        return render_template('user_create.html', admin=session.get('admin'))
    newUser = Users(name=request.form['username'], password=bcrypt.generate_password_hash(request.form['userPassword']))
    db.session.add(newUser)
    db.session.commit()
    db.session.refresh(newUser)   
    return render_template('success.html', topic='newUser', user=session.get('username'), admin=session.get('admin'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_user():
    if (request.method=='GET'):
        return render_template('admin_login.html', user=session.get('username'), admin=session.get('admin'))
    if (request.form['adminPassword'] != ADMIN_PASSWORD or request.form['adminName'] != ADMIN_NAME):
        return render_template('admin_login.html', errorCode='wrong-credentials', user=session.get('username'), admin=session.get('admin'))
    session.permanent = True
    session['admin'] = True
    if (not session.get('username')):
        session['username'] = 'Admin'
    return render_template('success.html', topic='admin-login', user=session.get('username'), admin=session.get('admin'))
    