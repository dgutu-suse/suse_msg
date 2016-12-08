#!/usr/bin/python3

import pika
import sys
import json
import logging

import os
import sys 

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
from suse_msg.ircclient import IRCClient
from suse_msg.router import Router
from suse_msg.msgfmt import MsgFormatter

logging.basicConfig(level=logging.INFO)

config = {
    "amqp": {
        "server": "amqp://guest:guest@kazhua.suse.de/",
        "exchange": "pubsub",
        "auto_reconnect": 5
    },
    "irc": {
        "server": "irc.suse.de",
        "port": 6697,
        "nickname": "hermes",
        "join_channels": False
    },
    "routing": {
        "*.info": ["#foobar123", "#foobar456"],
        "suse.#": ["#foobar123"]
    }
}



router = Router(config['routing'])
formatter = MsgFormatter()


join_channels = router.channels if config['irc']['join_channels'] else []
ircc = IRCClient(config['irc']['server'], config['irc']['port'], config['irc']['nickname'], join_channels)


def msg_cb(ch, method, properties, body):
    topic = method.routing_key
    try:
        body = body.decode("UTF-8")
        msg = json.loads(body)
    except ValueError:
        logging.warning("Invalid msg: %r -> %r" % (topic, body))
    else:
        print("%s: %s" % (topic, formatter.fmt(topic, msg, colors='xterm')))
        ircc.notice(formatter.fmt(topic, msg), router.topic_channels(topic))


while True:
    try:
        logging.info("Connecting to AMQP server")
        connection = pika.BlockingConnection(pika.URLParameters(config['amqp']['server']))
        channel = connection.channel()

        channel.exchange_declare(exchange=config['amqp']['exchange'], type='topic')

        result = channel.queue_declare(exclusive=True)
        queue_name = result.method.queue

        for binding_key in config['routing'].keys():
            channel.queue_bind(exchange=config['amqp']['exchange'], queue=queue_name, routing_key=binding_key)

        channel.basic_consume(msg_cb, queue=queue_name, no_ack=True)

        logging.info("Connected")
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        logging.warning("AMQP Connection failed: %s" % e)
        if config['amqp']['auto_reconnect']:
            time.sleep(config['amqp']['auto_reconnect'])
        else:
            raise
