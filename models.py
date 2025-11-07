from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    position = db.Column(db.String(100), nullable=False)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    opponent = db.Column(db.String(100), nullable=False)
    team_score = db.Column(db.Integer, nullable=True)
    opponent_score = db.Column(db.Integer, nullable=True)

class GameBattingOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    player = db.relationship('Player')
    game = db.relationship('Game')

class AtBatStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    order = db.Column(db.Integer)
    result = db.Column(db.String(20))
    inning = db.Column(db.Integer)
    rbis = db.Column(db.Integer, default=0)
    position = db.Column(db.String(20))
    note = db.Column(db.String(50))