"""
This file is the top level file for the Item Catalog project and
uses the Flask framework.
This project allows users to add items to categories. Users can also
edit and delete their own items.
JSON endpoints are provided for catalog, category, and item.
Authentication is handled by Google's OAuth API and Facebook's OAuth API.
This file contains routes and view functions.
"""

# imports for this project
from flask import Flask, render_template, request, redirect
from flask import jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem, User
from flask import session as login_session
from functools import wraps
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"


# Connect to Database and create database session
engine = create_engine('sqlite:///restaurantmenuwithusers.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

"""Login check decorator, used to check if the user is logged in or not.
If not logged in, then redirects the user to the login page
thus preventing unauthorized access to important data."""


def loginCheck(f):
    @wraps(f)
    def userLog(*args, **kwargs):
        if 'username' not in login_session:
            return redirect('/login')
        else:
            return f(*args, **kwargs)
    return userLog


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps(
            'Current user is already connected.'),
            200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: \
    150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output

    # DISCONNECT - Revoke a current user's token and reset their login_session


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    print 'In gdisconnect access token is %s', access_token
    print 'User name is:'
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
        % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view Restaurant Information
@app.route('/restaurants/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurants/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


# code for the home page
@app.route('/')
def restaurants():
    rest = session.query(Restaurant).all()
    if 'username' not in login_session:
        return render_template('homep.html', rest=rest)
    else:
        return render_template('home.html',
                               rest=rest, uname=login_session['username'])


# code to add new restaurant in the database
@app.route('/restaurant/new/', methods=['GET', 'POST'])
@loginCheck
def newRestaurant():
    if request.method == 'POST':
        newItem = Restaurant(
            name=request.form['name'], user_id=login_session.get('user_id'),
            picture=request.form['picture'])
        session.add(newItem)
        session.commit()
        return redirect(url_for('restaurants'))
    else:
        return render_template('newrestaurant.html',
                               uname=login_session['username'])


# code that will allow the authorized user to edit the restaurant
@app.route('/restaurant/<int:restaurant_id>/edit',
           methods=['GET', 'POST'])
@loginCheck
def editRestaurant(restaurant_id):
    editedItem = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if editedItem.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized to \
        delete this restaurant. Please create your own restaurant in order to \
        edit.');location.replace('http://localhost:5000/');}</script> \
        <body onload='myFunction()''>"

    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        session.add(editedItem)
        session.commit()
        return redirect(url_for('restaurants'))
    else:
        # USE THE RENDER_TEMPLATE FUNCTION BELOW TO SEE THE VARIABLES YOU
        # SHOULD USE IN YOUR EDITMENUITEM TEMPLATE
        return render_template(
            'editrestaurant.html', restaurant_id=restaurant_id,
            item=editedItem, uname=login_session['username'])


# code that will allow the authorized users to delete the restaurant
@app.route('/restaurant/<int:restaurant_id>/delete',
           methods=['GET', 'POST'])
@loginCheck
def deleteRestaurant(restaurant_id):
    itemToDelete = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if itemToDelete.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized \
        to delete this restaurant. Please create your own restaurant in order \
        to edit.');location.replace('http://localhost:5000/');}</script> \
        <body onload='myFunction()''>"

    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        return redirect(url_for('restaurants'))
    else:
        return render_template('deleterestaurant.html',
                               uname=login_session['username'],
                               item=itemToDelete)


# It displays the restaurant menu
@app.route('/restaurants/<int:restaurant_id>/')
def restaurantMenu(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant.id)
    if 'username' not in login_session:
        return render_template('menu_public.html', restaurant=restaurant,
                               items=items)
    else:

        return render_template('menu.html', uname=login_session['username'],
                               restaurant=restaurant, items=items)


# Create route for newMenuItem function here
@app.route('/restaurant/<int:restaurant_id>/new/', methods=['GET', 'POST'])
@loginCheck
def newMenuItem(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if restaurant.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized to \
        add new item to this restaurant. Please create your own restaurant in \
        order to edit.');location.replace(history.back());}</script><body \
        onload='myFunction()''>"

    if request.method == 'POST':
        newItem = MenuItem(
            name=request.form['name'], price=request.form['price'],
            description=request.form['description'],
            restaurant_id=restaurant_id, user_id=restaurant.user_id)
        session.add(newItem)
        session.commit()
        return redirect(url_for('restaurantMenu', restaurant_id=restaurant_id))
    else:
        return render_template('newitem.html', uname=login_session['username'],
                               restaurant_id=restaurant_id,
                               restaurant=restaurant)


# Create route for editMenuItem function here
@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/edit',
           methods=['GET', 'POST'])
@loginCheck
def editMenuItem(restaurant_id, menu_id):
    editedItem = session.query(MenuItem).filter_by(id=menu_id).one()
    if editedItem.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized\
        to edit this menu item. Please create your own restaurant in order to \
        edit.');location.replace(history.back());}</script><body \
        onload='myFunction()''>"

    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
            editedItem.price = request.form['price']
            editedItem.description = request.form['description']
        session.add(editedItem)
        session.commit()
        return redirect(url_for('restaurantMenu', restaurant_id=restaurant_id))
    else:
        # USE THE RENDER_TEMPLATE FUNCTION BELOW TO SEE THE VARIABLES YOU
        # SHOULD USE IN YOUR EDITMENUITEM TEMPLATE
        return render_template(
            'editmenu.html', uname=login_session['username'],
            restaurant_id=restaurant_id, menu_id=menu_id, item=editedItem)


# Create a route for viewMenu function here
@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/view')
def viewMenuItem(restaurant_id, menu_id):
    Item = session.query(MenuItem).filter_by(id=menu_id).one()
    if 'username' not in login_session:
        return render_template('viewitem_public.html',
                               restaurant_id=restaurant_id, menu_id=menu_id,
                               item=Item)
    else:
        return render_template(
            'viewitem.html', uname=login_session['username'],
            restaurant_id=restaurant_id, menu_id=menu_id, item=Item)


# create a route for deleting a menu item
@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/delete',
           methods=['GET', 'POST'])
@loginCheck
def deleteMenuItem(restaurant_id, menu_id):
    itemToDelete = session.query(MenuItem).filter_by(id=menu_id).one()
    if itemToDelete.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized \
        to delete this menu item. Please create your own restaurant in order \
        to edit.');location.replace(history.back());}</script><body \
        onload='myFunction()''>"

    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        return redirect(url_for('restaurantMenu', restaurant_id=restaurant_id))
    else:
        return render_template('deleteitem.html', item=itemToDelete,
                               uname=login_session['username'])


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
