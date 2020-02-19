from . import api, db, jwt
from .database import User, RevokedTokens

from flask import request
from flask_restful import Resource
from flask_jwt_extended import (create_access_token, create_refresh_token,
                               jwt_refresh_token_required, get_jwt_identity,
                               jwt_required, jwt_optional, get_raw_jwt)
from sqlalchemy.exc import IntegrityError

from re import search


@jwt.token_in_blacklist_loader
def check_if_token_in_blacklist(decrypted_token):
    # Check if tokens are in blacklist
    jti = decrypted_token['jti']

    return bool(RevokedTokens.query.filter_by(jti=jti).first())


class Ping(Resource):
    def get(self):
        return {"msg": "Working"}

class Login(Resource):
    def post(self):
        # fetch parameters
        try:
            username = str(request.form['username'])
            password = str(request.form['password'])
        except KeyError:
            return {"msg": "Missing parameter(s)"}, 400

        # check credentials
        try:
            user = User.check(username, password)
        except ValueError:
            return {"msg": "Wrong username or password"}, 400

        # return the token
        access = create_access_token(identity=user.username)
        refresh = create_refresh_token(identity=user.username)
        return {"msg": "Ok", "access_token": access, "refresh_token": refresh}

class Register(Resource):
    def post(self):
        # fetch parameters
        try:
            username = str(request.form['username'])
            name = str(request.form['name'])
            surname = str(request.form['surname'])            
            email = str(request.form['email'])
            password = str(request.form['password'])
        except KeyError:
            return {"msg": "Missing parameter(s)"}, 400

        # check parameters lenght
        if not len(username) > 4 or not len(password) > 4:
            return {"msg": "username and/or password too short"}, 400

        # check if email is an email
        elif not search(r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$', email):
            return {"msg": "Invalid email"}, 400

        # Try add it in the database
        try:
            User(username=username, name=name, surname=surname, email=email, password=password).save()

        # If it's already present in the db
        except IntegrityError:
            db.session.rollback()
            return {"msg": "Already registered"}, 400

        # if nothing goes wrong, return the token
        access = create_access_token(identity=username)
        refresh = create_refresh_token(identity=username)
        return {"msg": "Ok", "access_token": access, "refresh_token": refresh}

class Refresh(Resource):
    @jwt_refresh_token_required
    def post(self):
        username = get_jwt_identity()
        jti = get_raw_jwt()['jti']
        return {'msg': 'Ok', 'access_token': create_access_token(identity=username)}

class LogoutAccess(Resource):
    @jwt_required
    def post(self):
        jti = get_raw_jwt()['jti']
        exp = get_raw_jwt()['exp']
        RevokedTokens(jti=jti, exp=exp).save()
        return {'msg': 'Ok'}

class LogoutRefresh(Resource):
    @jwt_refresh_token_required
    def post(self):
        jti = get_raw_jwt()['jti']
        exp = get_raw_jwt()['exp']
        RevokedTokens(jti=jti, exp=exp).save()
        return {'msg': 'Ok'}

class ViewUser(Resource):
    @jwt_optional
    def get(self, username=None):
        # if username isn't specified, return your infos
        if not username:
            username = get_jwt_identity()

            # check if it's logged in
            if not username:
                return {"msg": "Missing Authorization Header"}, 401

            # fetch user infos and change something
            user = User.query.filter_by(username=username).first().json
            del user['id'], user['password']
            user['msg'] = "Ok"

            # return them
            return user

        # if a username is specified, check if exists
        user = User.query.filter_by(username=username).first()

        if not user:
            return {"msg": "User does not exist"}, 404

        # If it exists, fetch his public data
        user = user.json
        del user['id'], user['email'], user['password']
        user['msg'] = 'Ok'

        # return it
        return user



# Add resources to APIs
api.add_resource(Ping, '/', '/ping')
api.add_resource(Login, '/login')
api.add_resource(Register, '/register')
api.add_resource(Refresh, '/refresh')
api.add_resource(LogoutAccess, '/logout/access')
api.add_resource(LogoutRefresh, '/logout/refresh')
api.add_resource(ViewUser, '/user', '/user/<string:username>')
