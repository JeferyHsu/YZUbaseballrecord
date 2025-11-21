import os
from flask import Flask, render_template, request, redirect, url_for
from models import db, Player, Game, GameBattingOrder, AtBatStat, DefenseStat

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'test_secret_key'
db.init_app(app)

OUT_RESULTS = {'三振': 1, '不死三振': 0, '雙殺': 2, '外飛': 1, '內滾': 1, '內飛': 1, '犧牲': 1}

def calculate_outs(game_id, inning, source='atbat'):
    if source == 'atbat':
        records = AtBatStat.query.filter_by(game_id=game_id, inning=inning).all()
        outs = sum(OUT_RESULTS.get(r.result, 0) for r in records)
        # 加入跑者出局數
        outs += sum(1 for r in records if r.result == 'RUNNER_OUT')
    else:
        records = DefenseStat.query.filter_by(game_id=game_id, inning=inning).all()
        outs = sum(OUT_RESULTS.get(r.result, 0) for r in records)
        outs += sum(1 for r in records if r.result == 'RUNNER_OUT')
    return outs

def calculate_pitcher_stats(game_id):
    stats = DefenseStat.query.filter_by(game_id=game_id).all()
    pitcher_groups = {}
    for rec in stats:
        pid = rec.pitcher_id
        if pid not in pitcher_groups:
            pitcher_groups[pid] = {
                'name': Player.query.get(pid).name if pid else "",
                'pitcher_id': pid,
                'innings_outs': 0,          # 累出局數，最後自行轉為局數
                'batters': 0,
                'pitch_count': 0,
                'strikes': 0,
                'hits': 0,
                'hr': 0,
                'bb': 0,
                'hbp': 0,
                'k': 0,
                'run': 0
            }
        if rec.result != 'RUNNER_OUT':
            pitcher_groups[pid]['batters'] += 1
        pitcher_groups[pid]['pitch_count'] += rec.pitch_count
        pitcher_groups[pid]['strikes'] += rec.strike
        pitcher_groups[pid]['run'] += rec.runs
        # 判斷出局
        if rec.result in ['三振', '內滾', '外飛', '雙殺', '內飛', '犧牲']:
            pitcher_groups[pid]['innings_outs'] += (2 if rec.result == '雙殺' else 1)
        if rec.result == 'RUNNER_OUT':
            pitcher_groups[pid]['innings_outs'] += 1
        # 記錄安打 (可依你設計擴大)
        if rec.result in ['內安', '一安', '二安', '三安', '全壘']:
            pitcher_groups[pid]['hits'] += 1
        if rec.result == '全壘':
            pitcher_groups[pid]['hr'] += 1
        if rec.result == '四壞':
            pitcher_groups[pid]['bb'] += 1
        if rec.result == '觸身':
            pitcher_groups[pid]['hbp'] += 1
        if rec.result == '三振':
            pitcher_groups[pid]['k'] += 1
        # 記錄每局被得分 (需額外資訊可擴展)
    # 統計 Total
    total = {
        'name': "Total",
        'innings_outs': 0, 'batters': 0, 'pitch_count': 0, 'strikes': 0, 'hits': 0, 'hr': 0,
        'bb': 0, 'hbp': 0, 'k': 0, 'run': 0
    }
    for v in pitcher_groups.values():
        for key in total.keys():
            if key != 'name': total[key] += v[key]
    # 將局數（出局數）轉換為 1 2/3 這樣格式
    def format_ip(outs):
        full = outs // 3
        rem = outs % 3
        return f"{full} {rem}/3" if rem else str(full)
    for v in pitcher_groups.values():
        v['ip'] = format_ip(v['innings_outs'])
    total['ip'] = format_ip(total['innings_outs'])
    return list(pitcher_groups.values()), total

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
    completed_games = Game.query.filter_by(is_recorded=True).all()
    uncompleted_games = Game.query.filter_by(is_recorded=False).all()
    return render_template('index.html',
        completed_games=completed_games,
        uncompleted_games=uncompleted_games
    )


@app.route('/add_game', methods=['GET', 'POST'])
def add_game():
    if request.method == 'POST':
        tournament = request.form.get('tournament', '')
        date = request.form['date']
        opponent = request.form['opponent']
        first_attack = request.form['first_attack']
        game = Game(tournament=tournament,date=date, opponent=opponent, team_score=0, opponent_score=0, first_attack=first_attack)
        db.session.add(game)
        db.session.commit()
        return redirect(url_for('set_batting_order', game_id=game.id))
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
    DefenseStat.query.filter_by(game_id=game_id).delete()
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
    # 檢查是否已設定棒次
    ordered = GameBattingOrder.query.filter_by(game_id=game_id).count()
    if ordered > 0 and request.method == 'GET':
        # 已有紀錄的直接跳進攻/防守紀錄頁，不再顯示設定
        if game.first_attack == 'A':
            return redirect(url_for('record_atbat', game_id=game_id, order=0, inning=1))
        else:
            return redirect(url_for('record_defense', game_id=game_id, inning=1))
    if request.method == 'POST':
        GameBattingOrder.query.filter_by(game_id=game_id).delete()
        db.session.commit()
        for order in range(1, 10):
            pid = request.form.get(f'order_{order}')
            if pid:
                gbo = GameBattingOrder(game_id=game_id, player_id=int(pid), order=order-1)
                db.session.add(gbo)
        db.session.commit()
        # 進攻或防守
        if game.first_attack == 'A':
            return redirect(url_for('record_atbat', game_id=game_id, order=0, inning=1))
        else:
            return redirect(url_for('record_defense', game_id=game_id, inning=1))
    return render_template('set_batting_order.html', players=players, game=game)

@app.route('/record_atbat/<int:game_id>/<int:order>/<int:inning>', methods=['GET', 'POST'])
def record_atbat(game_id, order, inning):
    batting_orders = GameBattingOrder.query.filter_by(game_id=game_id).order_by(GameBattingOrder.order).all()
    total = len(batting_orders)
    if total == 0:
        return "請先設定棒次順序"
    order = int(order)
    inning = int(inning)
    current_batter = batting_orders[order]
    result_types = ['三振', '不死三振', '四壞', '觸身', '內安', '一安', '二安', '三安', '全壘', '失誤', '雙殺', '犧牲', '外飛', '內滾', '內飛', 'RUNNER_OUT']
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
        if selected_result == 'RUNNER_OUT':
        # 出局數+1，但不換下個打者
        # 直接重新顯示同一order和inning的頁面
            return redirect(url_for('record_atbat', game_id=game_id, order=order, inning=inning))
        if outs >= 3:
            if game.first_attack == 'A':
                # 先攻隊伍，進攻結束換防守，同局下半
                return redirect(url_for('record_defense', game_id=game_id, inning=inning))
            else:
                # 先守隊伍，進攻結束進入下一局上半防守
                return redirect(url_for('record_defense', game_id=game_id, inning=inning+1))
        return redirect(url_for('record_atbat', game_id=game_id, order=(order+1)%total, inning=inning))
    return render_template('record_atbat.html',
        batter=current_batter.player,
        order=order,
        inning=inning,
        is_top=(game.first_attack == 'A'),
        outs=outs,
        result_types=result_types,
        game_id=game_id,game=game,
        team_score=game.team_score,
        opponent_score=game.opponent_score,
        opponent=game.opponent)

@app.route('/record_defense/<int:game_id>/<int:inning>', methods=['GET', 'POST'])
def record_defense(game_id, inning):
    pitchers = Player.query.all()
    game = Game.query.get_or_404(game_id)
    last_batter_name = ""

    curr_pitcher_id = request.args.get('pitcher_id', type=int)
    if request.method == 'POST':
        curr_pitcher_id = request.form.get('pitcher_id', type=int)
    if curr_pitcher_id is None and pitchers:
        if getattr(game, 'current_pitcher_id', None):
            curr_pitcher_id = game.current_pitcher_id
        else:
            curr_pitcher_id = pitchers[0].id

    if request.method == 'POST':
        batter_name = request.form['batter_name']
        strike = int(request.form['strike'])
        ball = int(request.form['ball'])
        pitch_count = int(request.form['pitch_count'])
        result = request.form['result']
        runs = int(request.form.get('runs', 0))

        stat = DefenseStat(
            game_id=game_id, inning=inning,
            pitcher_id=curr_pitcher_id, batter_name=batter_name,
            strike=strike, ball=ball,
            pitch_count=pitch_count, result=result,
            runs=runs
        )
        db.session.add(stat)

        # 更新對手分數
        game.opponent_score = (game.opponent_score or 0) + runs
        game.current_pitcher_id = curr_pitcher_id
        db.session.commit()
        last_batter_name = batter_name

        # 計算outs時包含跑者出局 'RUNNER_OUT'
        records = DefenseStat.query.filter_by(game_id=game_id, inning=inning).all()
        outs = sum(OUT_RESULTS.get(r.result, 0) for r in records)
        outs += sum(1 for r in records if r.result == 'RUNNER_OUT')

        # 如果是跑者出局，留在同頁不跳轉不換投手
        if result == 'RUNNER_OUT':
            return redirect(url_for('record_defense', game_id=game_id, inning=inning, pitcher_id=curr_pitcher_id))

        # 三出局跳轉，確保只有POST時觸發
        if outs >= 3:
            if game.first_attack == 'A':
                return redirect(url_for('record_atbat', game_id=game_id, order=0, inning=inning+1, pitcher_id=curr_pitcher_id))
            else:
                return redirect(url_for('record_atbat', game_id=game_id, order=0, inning=inning, pitcher_id=curr_pitcher_id))

        # 其他情況續留防守頁面
        return redirect(url_for('record_defense', game_id=game_id, inning=inning, pitcher_id=curr_pitcher_id))
    
    # GET請求 - 計算各種投手用球數等現有邏輯，不變
    pitcher_pitch_count = 0
    if curr_pitcher_id:
        pitcher_pitch_count = sum(
            r.pitch_count
            for r in DefenseStat.query.filter_by(game_id=game_id).all()
            if r.pitcher_id == curr_pitcher_id
        )
    records = DefenseStat.query.filter_by(game_id=game_id, inning=inning).all()
    outs = sum(OUT_RESULTS.get(r.result, 0) for r in records)
    outs += sum(1 for r in records if r.result == 'RUNNER_OUT')

    inning_records = []
    for r in records:
        pitcher = Player.query.get(r.pitcher_id) if r.pitcher_id else None
        inning_records.append({
            "pitcher": pitcher,
            "batter_name": r.batter_name,
            "strike": r.strike,
            "ball": r.ball,
            "pitch_count": r.pitch_count,
            "result": r.result,
            "runs": r.runs
        })
        for rec in inning_records:
            if rec['result'] == 'RUNNER_OUT':
                rec['result'] = '跑者出局'

    total_pitch_this_inning = sum(r.pitch_count for r in records)
    total_pitch_all = sum(r.pitch_count for r in DefenseStat.query.filter_by(game_id=game_id).all())
    curr_pitcher_inning_pitch_count = sum(
        r.pitch_count
        for r in DefenseStat.query.filter_by(game_id=game_id, inning=inning, pitcher_id=curr_pitcher_id).all()
    )
    curr_pitcher = Player.query.get(curr_pitcher_id) if curr_pitcher_id else None

    return render_template('record_defense.html',
        game=game,
        game_id=game_id, inning=inning,
        pitchers=pitchers, curr_pitcher_id=curr_pitcher_id,curr_pitcher=curr_pitcher,
        last_batter_name=last_batter_name,
        inning_records=inning_records,
        is_top=(game.first_attack == 'D'),
        pitcher_pitch_count=pitcher_pitch_count,
        curr_pitcher_inning_pitch_count=curr_pitcher_inning_pitch_count,
        total_pitch_this_inning=total_pitch_this_inning,
        total_pitch_all=total_pitch_all,
        outs=outs
    )

@app.route('/choose_starting_pitcher/<int:game_id>', methods=['GET', 'POST'])
def choose_starting_pitcher(game_id):
    game = Game.query.get_or_404(game_id)
    pitchers = Player.query.all()
    if request.method == 'POST':
        pitcher_id = int(request.form['pitcher_id'])
        game.starting_pitcher_id = pitcher_id  # 可以加在 Game model 記錄
        db.session.commit()
        # 根據先攻/先守決定流程
        if game.first_attack == 'A':
            return redirect(url_for('record_atbat', game_id=game_id, order=0, inning=1))
        else:
            return redirect(url_for('record_defense', game_id=game_id, inning=1))
    return render_template('choose_starting_pitcher.html', game=game, pitchers=pitchers)

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

@app.route('/switch_player/<int:game_id>/<int:order>', methods=['GET', 'POST'])
def switch_player(game_id,order):
    #order = request.args.get('order') if request.method == 'GET' else request.form.get('order')
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
        return redirect(url_for('record_atbat', game_id=game_id, order=order, inning=get_current_inning(game_id)))
    return render_template('switch_player.html', batting_orders=batting_orders,
                           all_players=all_players, game_id=game_id, order=order)

@app.route('/switch_pitcher/<int:game_id>/<int:inning>', methods=['GET', 'POST'])
def switch_pitcher(game_id, inning):
    pitchers = Player.query.all()
    game = Game.query.get_or_404(game_id)
    if request.method == 'POST':
        new_pitcher_id = int(request.form['pitcher_id'])
        game.current_pitcher_id = new_pitcher_id      # 關鍵！寫入Game紀錄
        db.session.commit()
        # 換投後帶著新的投手ID跳回record_defense
        return redirect(url_for('record_defense', game_id=game_id, inning=inning, pitcher_id=new_pitcher_id))
    return render_template('switch_pitcher.html', pitchers=pitchers, game_id=game_id, inning=inning)

def get_stats_table(game_id):
    atbats = AtBatStat.query.filter_by(game_id=game_id).all()
    innings = sorted(set([a.inning for a in atbats]))
    max_inning = max(innings) if innings else 9
    groups = {}
    total = {'ab': 0, 'hit': 0, 'hr': 0, 'rbi': 0, 'run': 0, 'inning_results': [0 for _ in range(max_inning)]}
    for ab in atbats:
        if ab.result == 'RUNNER_OUT':
            continue
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
    stats_table, max_inning, total = get_stats_table(game_id)      # 打擊數據用

    defense_stats = DefenseStat.query.filter_by(game_id=game_id).order_by(DefenseStat.inning, DefenseStat.id).all()
    defense_records = []
    for r in defense_stats:
        pitcher = Player.query.get(r.pitcher_id) if r.pitcher_id else None
        defense_records.append({
            "inning": r.inning,
            "pitcher": pitcher,
            "batter_name": r.batter_name,
            "strike": r.strike,
            "ball": r.ball,
            "pitch_count": r.pitch_count,
            "result": r.result
        })
    pitcher_stats, pitcher_total = calculate_pitcher_stats(game_id)   # 投手數據用

    # ==== 新增投手每局用球數表格計算 ====
    pitchers = {r.pitcher_id: Player.query.get(r.pitcher_id).name for r in defense_stats if r.pitcher_id}
    innings = sorted(set([r.inning for r in defense_stats]))
    pitcher_inning_data = []
    for pid, pname in pitchers.items():
        per_inning = []
        for inn in innings:
            count = sum(r.pitch_count for r in defense_stats if r.pitcher_id == pid and r.inning == inn)
            per_inning.append(count if count != 0 else "")
        pitcher_inning_data.append({
            "name": pname,
            "data": per_inning
        })
    # innings: 1,2,...N  pitcher_inning_data: list of {name, [n局,n局,...]}
    
    return render_template('game_detail.html',
        game=game,
        stats_table=stats_table,
        max_inning=max_inning,
        total=total,                  # for 打擊
        defense_records=defense_records,
        pitcher_stats=pitcher_stats,
        pitcher_total=pitcher_total,  # for 投手
        pitcher_innings=innings,      # 表頭局數
        pitcher_inning_data=pitcher_inning_data  # 表格內容
    )

@app.route('/record_match_select')
def record_match_select():
    games = Game.query.filter_by(is_recorded=False).all()
    return render_template('record_match_select.html', games=games)

@app.route('/finish_record/<int:game_id>', methods=['POST'])
def finish_record(game_id):
    game = Game.query.get_or_404(game_id)
    game.is_recorded = True
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

with app.app_context():
    db.create_all()
