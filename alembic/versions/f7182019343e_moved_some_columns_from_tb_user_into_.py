"""Moved some columns from tb_user into redis

Revision ID: f7182019343e
Revises: 25cf8a00d471
Create Date: 2016-04-21 21:13:55.112463

"""

# revision identifiers, used by Alembic.
revision = 'f7182019343e'
down_revision = '25cf8a00d471'
branch_labels = None
depends_on = None

import argparse

from alembic import context
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import relationship
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String

from pajbot.tbutil import load_config
from pajbot.managers import RedisManager

Session = sessionmaker()

Base = declarative_base()

tag = context.get_tag_argument()

parser = argparse.ArgumentParser()
parser.add_argument('--config', '-c',
                    default='config.ini',
                    help='Specify which config file to use '
                            '(default: config.ini)')
custom_args = None
if tag is not None:
    custom_args = tag.replace('"', '').split()
args, unknown = parser.parse_known_args(args=custom_args)

pb_config = load_config(args.config)

redis_options = {}
if 'redis' in pb_config:
    redis_options = pb_config._sections['redis']

RedisManager.init(**redis_options)


class User(Base):
    __tablename__ = 'tb_user'

    id = Column(Integer, primary_key=True)
    username = Column(String(128), nullable=False, index=True, unique=True)
    username_raw = Column(String(128))
    level = Column(Integer, nullable=False, default=100)
    points = Column(Integer, nullable=False, default=0)
    num_lines = Column(Integer, nullable=False, default=0)
    subscriber = Column(Boolean, nullable=False, default=False)
    _last_seen = Column('last_seen', DateTime)
    _last_active = Column('last_active', DateTime)
    minutes_in_chat_online = Column(Integer, nullable=False, default=0)
    minutes_in_chat_offline = Column(Integer, nullable=False, default=0)
    ignored = Column(Boolean, nullable=False, default=False)
    banned = Column(Boolean, nullable=False, default=False)


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    config_data = RedisManager.get().config_get('maxmemory')
    max_memory = config_data['maxmemory']
    print('redis max memory: {}'.format(max_memory))
    RedisManager.get().config_set('maxmemory', str(int(max_memory) * 10))
    with RedisManager.pipeline_context() as pipeline:
        streamer = pb_config['main']['streamer']

        num_lines_key = '{streamer}:users:num_lines'.format(streamer=streamer)
        ignored_key = '{streamer}:users:ignored'.format(streamer=streamer)
        last_active_key = '{streamer}:users:last_active'.format(streamer=streamer)
        last_seen_key = '{streamer}:users:last_seen'.format(streamer=streamer)
        banned_key = '{streamer}:users:banned'.format(streamer=streamer)
        username_raw_key = '{streamer}:users:username_raw'.format(streamer=streamer)
        pipeline.delete(num_lines_key, ignored_key, last_active_key, last_seen_key, banned_key, username_raw_key)

        for user in session.query(User):
            if user.num_lines > 0:
                pipeline.zadd(num_lines_key, user.username, user.num_lines)

            if user.ignored:
                pipeline.hset(ignored_key, user.username, 1)

            if user.banned:
                pipeline.hset(banned_key, user.username, 1)

            if user.username != user.username_raw:
                pipeline.hset(username_raw_key, user.username, user.username_raw)

            if user._last_seen:
                pipeline.hset(last_seen_key, user.username, user._last_seen.timestamp())

            if user._last_active:
                pipeline.hset(last_active_key, user.username, user._last_active.timestamp())

    RedisManager.get().config_set('maxmemory', int(max_memory))

    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tb_user') as batch_op:
        batch_op.drop_column('num_lines')
        batch_op.drop_column('ignored')
        batch_op.drop_column('last_active')
        batch_op.drop_column('last_seen')
        batch_op.drop_column('banned')
    ### end Alembic commands ###

    session.commit()


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tb_user') as batch_op:
        batch_op.add_column(sa.Column('banned', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('last_seen', mysql.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('last_active', mysql.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('ignored', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('num_lines', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False))
    ### end Alembic commands ###
