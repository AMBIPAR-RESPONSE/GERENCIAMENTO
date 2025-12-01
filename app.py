# app.py
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'fleet.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# -------------------------
# Models
# -------------------------
class Aeronave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(64), unique=True, nullable=False)
    numero_serie = db.Column(db.String(128))
    fabricante = db.Column(db.String(128))
    modelo = db.Column(db.String(128))
    categoria = db.Column(db.String(64))
    base_operacional = db.Column(db.String(128))
    observacoes = db.Column(db.Text)
    status_atual = db.Column(db.String(32), default='solo')  # voando | solo | hangar | manutencao
    localizacao_atual = db.Column(db.String(128))
    comandante = db.Column(db.String(128))
    copiloto = db.Column(db.String(128))
    mecanico = db.Column(db.String(128))
    missao = db.Column(db.Text)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'matricula': self.matricula,
            'numero_serie': self.numero_serie,
            'fabricante': self.fabricante,
            'modelo': self.modelo,
            'categoria': self.categoria,
            'base_operacional': self.base_operacional,
            'observacoes': self.observacoes,
            'status_atual': self.status_atual,
            'localizacao_atual': self.localizacao_atual,
            'comandante': self.comandante,
            'copiloto': self.copiloto,
            'mecanico': self.mecanico,
            'missao': self.missao,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None
        }


class Manutencao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aeronave_id = db.Column(db.Integer, db.ForeignKey('aeronave.id'), nullable=False)
    data_agendada = db.Column(db.Date, nullable=False)
    duracao_dias = db.Column(db.Integer, default=1)
    status = db.Column(db.String(32), default='programada')  # programada | em_andamento | concluida

    aeronave = db.relationship('Aeronave', backref='manutencoes')


class HistoricoSituacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aeronave_id = db.Column(db.Integer, db.ForeignKey('aeronave.id'), nullable=False)
    status = db.Column(db.String(32))
    localizacao = db.Column(db.String(128))
    comandante = db.Column(db.String(128))
    copiloto = db.Column(db.String(128))
    mecanico = db.Column(db.String(128))
    missao = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    aeronave = db.relationship('Aeronave', backref='historico')


# -------------------------
# Inicializar DB (cria se não existir)
# -------------------------
@app.before_first_request
def create_tables():
    db.create_all()


# -------------------------
# Rotas - páginas
# -------------------------
@app.route('/')
def dashboard():
    # contadores simples
    total = Aeronave.query.count()
    em_manutencao = Aeronave.query.filter(Aeronave.status_atual == 'manutencao').count()
    voando = Aeronave.query.filter(Aeronave.status_atual == 'voando').count()
    proximas = Manutencao.query.order_by(Manutencao.data_agendada).limit(5).all()
    manut_cards = Aeronave.query.filter(Aeronave.status_atual == 'manutencao').limit(6).all()
    return render_template('dashboard.html',
                           total=total,
                           em_manutencao=em_manutencao,
                           voando=voando,
                           proximas=proximas,
                           manut_cards=manut_cards)


@app.route('/frota')
def frota():
    status_filter = request.args.get('status', 'todas')  # opcional
    q = Aeronave.query
    if status_filter and status_filter != 'todas':
        q = q.filter(Aeronave.status_atual == status_filter)
    aeronaves = q.order_by(Aeronave.matricula).all()
    return render_template('frota.html', aeronaves=aeronaves)


# -------------------------
# Rotas - ações / API simples (form posts / fetch)
# -------------------------
@app.route('/aeronave/nova', methods=['POST'])
def nova_aeronave():
    data = request.form
    a = Aeronave(
        matricula=data.get('matricula'),
        numero_serie=data.get('numero_serie'),
        fabricante=data.get('fabricante'),
        modelo=data.get('modelo'),
        categoria=data.get('categoria'),
        base_operacional=data.get('base_operacional'),
        observacoes=data.get('observacoes'),
        status_atual='solo'
    )
    db.session.add(a)
    db.session.commit()
    return redirect(url_for('frota'))


@app.route('/aeronave/<int:id>/atualizar', methods=['POST'])
def atualizar_aeronave(id):
    a = Aeronave.query.get_or_404(id)
    data = request.form
    # atualizar campos editáveis
    a.status_atual = data.get('status_atual', a.status_atual)
    a.localizacao_atual = data.get('localizacao_atual', a.localizacao_atual)
    a.comandante = data.get('comandante', a.comandante)
    a.copiloto = data.get('copiloto', a.copiloto)
    a.mecanico = data.get('mecanico', a.mecanico)
    a.missao = data.get('missao', a.missao)
    a.atualizado_em = datetime.utcnow()

    # salvar histórico
    hist = HistoricoSituacao(
        aeronave_id=a.id,
        status=a.status_atual,
        localizacao=a.localizacao_atual,
        comandante=a.comandante,
        copiloto=a.copiloto,
        mecanico=a.mecanico,
        missao=a.missao
    )
    db.session.add(hist)

    db.session.commit()
    return redirect(url_for('frota'))


@app.route('/manutencao/agendar', methods=['POST'])
def agendar_manutencao():
    data = request.form
    aeronave_id = int(data.get('aeronave_id'))
    data_agendada = datetime.strptime(data.get('data_agendada'), '%Y-%m-%d').date()
    duracao = int(data.get('duracao_dias') or 1)
    m = Manutencao(aeronave_id=aeronave_id, data_agendada=data_agendada, duracao_dias=duracao)
    db.session.add(m)
    # opcional: marcar aeronave como programada/manutencao
    a = Aeronave.query.get(aeronave_id)
    if a:
        a.status_atual = 'manutencao'
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/aeronave/<int:id>/excluir', methods=['POST'])
def excluir_aeronave(id):
    a = Aeronave.query.get_or_404(id)
    # deletar dependências (manutenções / historico)
    Manutencao.query.filter_by(aeronave_id=a.id).delete()
    HistoricoSituacao.query.filter_by(aeronave_id=a.id).delete()
    db.session.delete(a)
    db.session.commit()
    return redirect(url_for('frota'))


# -------------------------
# Rotas - endpoints JSON (para consumo via fetch se quiser)
# -------------------------
@app.route('/api/aeronaves')
def api_aeronaves():
    rows = Aeronave.query.order_by(Aeronave.matricula).all()
    return jsonify([r.to_dict() for r in rows])


@app.route('/api/aeronaves/<int:id>')
def api_get_aeronave(id):
    a = Aeronave.query.get_or_404(id)
    return jsonify(a.to_dict())


# -------------------------
# Util: inicializar exemplo (apenas para DEV)
# -------------------------
@app.route('/seed')
def seed():
    if Aeronave.query.count() > 0:
        return "Já populado"
    exemplos = [
        dict(matricula='PP-ECE', fabricante='Helibras', modelo='AS 350 BA', status_atual='voando', localizacao_atual='Surucucu', comandante='Carlos', copiloto='Moraes', mecanico='Mascarenhas', missao='Cestas SWUQ'),
        dict(matricula='PT-HLP', fabricante='Helibras', modelo='HB-350B', status_atual='voando', localizacao_atual='Surucucu', comandante='Charles', copiloto='', mecanico='Rafael', missao='Translado SWUQ SD6X'),
        dict(matricula='PS-AMB', fabricante='Airbus', modelo='AS 350 B2', status_atual='manutencao', localizacao_atual='Malboro'),
    ]
    for e in exemplos:
        a = Aeronave(**e)
        db.session.add(a)
    db.session.commit()
    return "Seed OK"


# -------------------------
# Run
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)
