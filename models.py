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
    current_pitcher_id = db.Column(db.Integer, nullable=True)
    first_attack = db.Column(db.String(1))  # 'A': 先攻, 'D': 先守
    is_recorded = db.Column(db.Boolean, default=False)
    tournament = db.Column(db.String)
    next_batter_order = db.Column(db.Integer, default=0)
    
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
    
class DefenseStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    inning = db.Column(db.Integer)
    pitcher_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    batter_name = db.Column(db.String(32))   # 可以另外設 Player 或只記名
    strike = db.Column(db.Integer)
    ball = db.Column(db.Integer)
    pitch_count = db.Column(db.Integer)
    result = db.Column(db.String(24))        # 打席結果
    runs = db.Column(db.Integer, default=0)  # 失分
