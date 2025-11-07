from flask import Flask, render_template, request, redirect, url_for
from models import db, Player, Game, GameBattingOrder, AtBatStat

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baseball.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'test_secret_key'
db.init_app(app)

OUT_RESULTS = {'三振': 1, '雙殺': 2, '外飛': 1, '內滾': 1, '內飛': 1, '犧牲': 1}

def calculate_outs(game_id, inning):
    atbats = AtBatStat.query.filter_by(game_id=game_id, inning=inning).all()
    outs = sum(OUT_RESULTS.get(ab.result, 0) for ab in atbats)
    return outs

def get_current_inning(game_id):
    atbats = AtBatStat.query.filter_by(game_id=game_id).all()
    if not atbats:
        return 1
    inning_outs = {}
    for ab in atbats:
        inning_outs.setdefault(ab.inning, 0)
        inning_outs[ab.inning] += OUT_RESULTS.get(ab.result, 0)
    max_inning = max(inning_outs.keys())
    if inning_outs[max_inning] < 3:
        return max_inning
    return max_inning + 1

@app.route('/')
def index():
    games = Game.query.all()
    return render_template('index.html', games=games)

@app.route('/add_game', methods=['GET', 'POST'])
def add_game():
    if request.method == 'POST':
        date = request.form['date']
        opponent = request.form['opponent']
        game = Game(date=date, opponent=opponent, team_score=0, opponent_score=0)
        db.session.add(game)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_game.html')

@app.route('/players')
def players():
    player_list = Player.query.all()
    return render_template('players.html', players=player_list)

@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        number = request.form['number']
        position = request.form['position']
        player = Player(name=name, number=number, position=position)
        db.session.add(player)
        db.session.commit()
        return redirect(url_for('players'))
    return render_template('add_player.html')

@app.route('/delete_player/<int:id>')
def delete_player(id):
    player = Player.query.get(id)
    db.session.delete(player)
    db.session.commit()
    return redirect(url_for('players'))

@app.route('/games')
def games():
    games = Game.query.all()
    return render_template('games.html', games=games)

@app.route('/delete_game/<int:game_id>')
def delete_game(game_id):
    AtBatStat.query.filter_by(game_id=game_id).delete()
    GameBattingOrder.query.filter_by(game_id=game_id).delete()
    db.session.commit()
    game = Game.query.get(game_id)
    if game:
        db.session.delete(game)
        db.session.commit()
    return redirect(url_for('games'))

@app.route('/set_batting_order/<int:game_id>', methods=['GET', 'POST'])
def set_batting_order(game_id):
    game = Game.query.get_or_404(game_id)
    players = Player.query.all()
    if request.method == 'POST':
        GameBattingOrder.query.filter_by(game_id=game_id).delete()
        db.session.commit()
        bat_orders = []
        # 收集「棒次排定」字段，並排好順序
        for player in players:
            order_num = request.form.get(f'order_{player.id}')
            if order_num:
                bat_orders.append((int(order_num)-1, player.id))  # 重要，order-1，確保從0開始 (前端輸入一般是從1開始)
        bat_orders.sort()
        # 創建所有棒次，order值是0,1,2,3...
        for idx, (order_idx, player_id) in enumerate(bat_orders):
            gbo = GameBattingOrder(game_id=game_id, player_id=player_id, order=idx)
            db.session.add(gbo)
        db.session.commit()
        print("DEBUG: GameBattingOrder after set_batting_order")
        for gbo in GameBattingOrder.query.filter_by(game_id=game_id).order_by(GameBattingOrder.order).all():
            print(f"order={gbo.order}, player_id={gbo.player_id}")
        return redirect(url_for('record_atbat', game_id=game_id, order=0, inning=1))
    return render_template('set_batting_order.html', players=players, game=game)

@app.route('/record_atbat/<int:game_id>/', defaults={'order':None, 'inning':None}, methods=['GET', 'POST'])
@app.route('/record_atbat/<int:game_id>/<int:order>/', defaults={'inning':None}, methods=['GET', 'POST'])
@app.route('/record_atbat/<int:game_id>/<int:order>/<int:inning>', methods=['GET', 'POST'])
def record_atbat(game_id, order, inning):
    batting_orders = GameBattingOrder.query.filter_by(game_id=game_id).order_by(GameBattingOrder.order).all()
    total = len(batting_orders)
    if inning is None:
        inning = get_current_inning(game_id)
    if total == 0:
        return "請先設定棒次順序"
    if order is None:
        if inning > 1:
            last_prev = AtBatStat.query.filter_by(game_id=game_id, inning=inning-1).order_by(AtBatStat.id.desc()).first()
            if last_prev:
                order = (last_prev.order + 1) % total
            else:
                order = 0
        else:
            order = 0
    order = int(order)
    if order >= total:
        order = total-1
    if order < 0:
        order = 0
    current_batter = batting_orders[order]
    result_types = ['三振', '四壞', '觸身', '內安', '一安', '二安', '三安', '全壘', '失誤', '雙殺', '犧牲', '外飛', '內滾', '內飛']
    game = Game.query.get_or_404(game_id)
    outs = calculate_outs(game_id, inning)
    if request.method == 'POST':
        selected_result = request.form['result']
        rbis = int(request.form.get('rbis', 0))
        position = request.form.get('position', '')
        note = request.form.get('note', '')
        atbat = AtBatStat(
            game_id=game_id,
            player_id=current_batter.player_id,
            order=current_batter.order,
            result=selected_result,
            inning=inning,
            rbis=rbis,
            position=position,
            note=note
        )
        db.session.add(atbat)
        if rbis > 0:
            game.team_score = (game.team_score or 0) + rbis
        db.session.commit()
        outs = calculate_outs(game_id, inning)
        if outs >= 3:
            next_order = (order + 1) % total
            return redirect(url_for('record_atbat', game_id=game_id, order=next_order, inning=inning+1))
        return redirect(url_for('record_atbat', game_id=game_id, order=(order+1)%total, inning=inning))
    return render_template('record_atbat.html',
        batter=current_batter.player,
        order=order,
        inning=inning,
        outs=outs,
        result_types=result_types,
        game_id=game_id,
        team_score=game.team_score,
        opponent_score=game.opponent_score,
        opponent=game.opponent)

@app.route('/undo_atbat/<int:game_id>/<int:order>/<int:inning>')
def undo_atbat(game_id, order, inning):
    atbat = (AtBatStat.query
             .filter_by(game_id=game_id, order=order, inning=inning)
             .order_by(AtBatStat.id.desc())
             .first())
    if atbat:
        game = Game.query.get(game_id)
        if atbat.rbis > 0 and game.team_score:
            game.team_score = max(0, game.team_score - atbat.rbis)
        db.session.delete(atbat)
        db.session.commit()
        prev_order = order - 1 if order > 0 else (len(GameBattingOrder.query.filter_by(game_id=game_id).all()) - 1)
        return redirect(url_for('record_atbat', game_id=game_id, order=prev_order, inning=inning))
    else:
        prev_order = order - 1 if order > 0 else (len(GameBattingOrder.query.filter_by(game_id=game_id).all()) - 1)
        return redirect(url_for('record_atbat', game_id=game_id, order=prev_order, inning=inning))

@app.route('/switch_player/<int:game_id>', methods=['GET', 'POST'])
def switch_player(game_id):
    order = request.args.get('order') if request.method == 'GET' else request.form.get('order')
    batting_orders = GameBattingOrder.query.filter_by(game_id=game_id).order_by(GameBattingOrder.order).all()
    all_players = Player.query.all()
    if order is None:
        order = 0
    order = int(order)
    if order >= len(batting_orders):
        order = len(batting_orders) - 1
    if order < 0:
        order = 0
    if request.method == 'POST':
        new_player_id = int(request.form['new_player'])
        gbo = GameBattingOrder.query.filter_by(game_id=game_id, order=order).first()
        if gbo:
            gbo.player_id = new_player_id
            db.session.commit()
        # debug check
        print("DEBUG: GameBattingOrder after switch_player")
        for gbo2 in GameBattingOrder.query.filter_by(game_id=game_id).order_by(GameBattingOrder.order).all():
            print(f"order={gbo2.order}, player_id={gbo2.player_id}")
        return redirect(url_for('record_atbat', game_id=game_id, order=order, inning=get_current_inning(game_id)))
    return render_template('switch_player.html', batting_orders=batting_orders,
                           all_players=all_players, game_id=game_id, order=order)

def get_stats_table(game_id):
    atbats = AtBatStat.query.filter_by(game_id=game_id).all()
    innings = sorted(set([a.inning for a in atbats]))
    max_inning = max(innings) if innings else 9
    groups = {}
    total = {'ab': 0, 'hit': 0, 'hr': 0, 'rbi': 0, 'run': 0, 'inning_results': [0 for _ in range(max_inning)]}
    for ab in atbats:
        key = (ab.order, ab.player_id, ab.note or '', ab.position or '')
        if key not in groups:
            groups[key] = {
                "order": ab.order,
                "player": Player.query.get(ab.player_id),
                "note": ab.note or "",
                "position": ab.position or "",
                "results": [""] * max_inning,
                "ab": 0, "hit": 0, "hr": 0, "rbi": 0
            }
        idx = ab.inning - 1
        groups[key]["results"][idx] += ("/" if groups[key]["results"][idx] else "") + (ab.result or "")
        if ab.result not in ['四壞', '觸身', '犧牲']:
            groups[key]["ab"] += 1
            total['ab'] += 1
        if ab.result in ['內安', '一安', '二安', '三安', '全壘']:
            groups[key]["hit"] += 1
            total['hit'] += 1
        if ab.result == '全壘':
            groups[key]["hr"] += 1
            total['hr'] += 1
        if ab.rbis:
            groups[key]["rbi"] += ab.rbis
            total['rbi'] += ab.rbis
    stats_table = list(groups.values())
    return stats_table, max_inning, total

@app.route('/game_detail/<int:game_id>')
def game_detail(game_id):
    game = Game.query.get_or_404(game_id)
    stats_table, max_inning, total = get_stats_table(game_id)
    return render_template('game_detail.html', game=game, stats_table=stats_table, max_inning=max_inning, total=total)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
