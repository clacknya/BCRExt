#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import datetime
import lxml.html

from hoshino import Service
from hoshino.typing import CQEvent
from hoshino.aiorequests import get

URL_CALENDAR = 'https://static.biligame.com/pcr/gw/calendar.js'

TIMEAPAN = {
	'国服日程表':     7,
	'国服月日程':     31,
	'国服周日程':     7,
	'国服日程':       1,
	'国服今日活动':   1,
}

sv = Service('公主连结国服日程表',
	help_='\n'.join([f'[{k}] 查询最长{TIMEAPAN[k]}天日程' for k in TIMEAPAN]))

async def get_raw_data() -> list:
	sv.logger.info(f'GET {URL_CALENDAR}')
	r = await get(URL_CALENDAR)
	m = re.search(r'\bdata\s*=\s*(?=\[)(?P<json>.+)(?<=\])', await r.text, flags=re.DOTALL)
	if m is not None:
		raw_string = m.group('json')
		# remove trailing commas
		std_string = re.sub(r',\s*(}|\])', r'\1', raw_string)
		return json.loads(std_string)
	else:
		raise Exception('regex search failed!')
	return None

def parse_raw_data(raw_data: list) -> dict:
	if raw_data is None:
		raise Exception('raw data not found!')
	data = {}
	for item in raw_data:
		year = int(item['year'])
		month = int(item['month'])
		if year not in data:
			data[year] = {}
		if month not in data[year]:
			data[year][month] = {}
		for key, value in item['day'].items():
			day = int(key)
			data[year][month][day] = value
	return data

def get_calendar(data: dict, limit: int=31) -> str:
	result = []
	# CST timezone
	now = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=+8)))
	for days in range(limit):
		date = now + datetime.timedelta(days=days)
		temp = data.get(date.year, {})
		temp = temp.get(date.month, {})
		temp = temp.get(date.day, {})
		if not temp: break
		info = []
		for key, value in temp.items():
			# "qdhd": 庆典活动
			# "tdz":  团队战
			# "tbhd": 特别活动
			# "jqhd": 剧情活动
			# "jssr": 角色生日
			if value and key in ['qdhd', 'tdz', 'tbhd', 'jqhd', 'jssr']:
				html = lxml.html.fromstring(value)
				nodes = html.cssselect('.cl-t')
				for node in nodes:
					info.append(node.text)
		msg = '\n'.join(info)
		if not msg: break
		result.append('\n'.join(['----------', date.strftime('%Y-%m-%d'), msg]))
	return '\n'.join(result)

async def scheduled_data():
	# update once everyday
	if (not hasattr(scheduled_data, 'data')) or \
		(not hasattr(scheduled_data, 'cdtime')) or \
		(datetime.datetime.now() > scheduled_data.cdtime):
		scheduled_data.data = parse_raw_data(await get_raw_data())
		scheduled_data.cdtime = datetime.datetime.now() + datetime.timedelta(hours=23)
	return scheduled_data.data

@sv.on_fullmatch(TIMEAPAN.keys())
async def calendar(bot, ev: CQEvent):
	msg = get_calendar(await scheduled_data(), limit=TIMEAPAN[ev['prefix']])
	await bot.send(ev, msg, at_sender=False)
