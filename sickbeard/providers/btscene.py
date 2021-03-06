# coding=utf-8
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import base64
import re
import traceback
import urllib

from . import generic
from sickbeard import logger
from sickbeard.bs4_parser import BS4Parser
from sickbeard.helpers import tryInt
from lib.unidecode import unidecode


class BTSceneProvider(generic.TorrentProvider):

    def __init__(self):
        generic.TorrentProvider.__init__(self, 'BTScene')

        self.url_home = ['https://%s/' % base64.b64decode(x) for x in [''.join(x) for x in [
            [re.sub('[o\sv]+', '', x[::-1]) for x in [
                'z Rn Y', 'uVv2vY', '1 5vSZ', 'sJ omb', 'rNov2b', 'uQoWvZ', '0FvoGb']],
            [re.sub('[v\sp]+', '', x[::-1]) for x in [
                'zRnp Y', 'upVp2Y', '15SvpZ', 'spJpmb', 'r N 2b', 'u QvWZ', '=Mvm d']],
        ]]]
        self.url_vars = {'search': '?q=%s&order=1', 'browse': 'lastdaycat/type/Series/',
                         'get': 'torrentdownload.php?id=%s'}
        self.url_tmpl = {'config_provider_home_uri': '%(home)s', 'search': '%(vars)s',
                         'browse': '%(home)s%(vars)s', 'get': '%(home)s%(vars)s'}

        self.minseed, self.minleech = 2 * [None]
        self.confirmed = False

    @staticmethod
    def _has_signature(data=None):
        return data and re.search(r'(?i)(?:btscene|bts[-]official|full\sindex)', data)

    def _search_provider(self, search_params, **kwargs):

        results = []
        if not self.url:
            return results

        items = {'Cache': [], 'Season': [], 'Episode': [], 'Propers': []}

        rc = dict((k, re.compile('(?i)' + v)) for (k, v) in {
            'info': '\w+?(\d+)[.]html', 'verified': 'Verified'}.iteritems())

        url = self.url
        response = self.get_url(url)
        if self.should_skip() or not response:
            return results

        form = re.findall('(?is)(<form[^>]+)', response)
        response = any(form) and form[0] or response
        action = re.findall('<form[^>]+action=[\'"]([^\'"]*)', response)[0]
        url = action if action.startswith('http') else \
            url if not action else \
            (url + action) if action.startswith('?') else \
            self.urls['config_provider_home_uri'] + action.lstrip('/')

        for mode in search_params.keys():
            for search_string in search_params[mode]:

                search_string = isinstance(search_string, unicode) and unidecode(search_string) or search_string

                search_url = self.urls['browse'] if 'Cache' == mode \
                    else url + self.urls['search'] % (urllib.quote_plus(search_string))

                html = self.get_url(search_url)
                if self.should_skip():
                    return results

                cnt = len(items[mode])
                try:
                    if not html or self._has_no_results(html):
                        raise generic.HaltParseException
                    with BS4Parser(html, features=['html5lib', 'permissive']) as soup:
                        torrent_rows = soup.select('tr[class$="_tr"]')

                        if not len(torrent_rows):
                            raise generic.HaltParseException

                        head = None
                        for tr in torrent_rows:
                            cells = tr.find_all('td')
                            if 6 > len(cells):
                                continue
                            try:
                                head = head if None is not head else self._header_row(tr)
                                seeders, leechers, size = [tryInt(n, n) for n in [
                                    cells[head[x]].get_text().strip() for x in 'seed', 'leech', 'size']]
                                if self._peers_fail(mode, seeders, leechers) or \
                                        self.confirmed and not (tr.find('img', src=rc['verified'])
                                                                or tr.find('img', title=rc['verified'])):
                                    continue

                                info = tr.find('a', href=rc['info'])
                                title = info and info.get_text().strip()
                                tid_href = info and rc['info'].findall(info['href'])
                                tid_href = tid_href and tryInt(tid_href[0], 0) or 0
                                tid_tr = tryInt(tr['id'].strip('_'), 0)
                                tid = (tid_tr, tid_href)[tid_href > tid_tr]

                                download_url = info and (self.urls['get'] % tid)
                            except (AttributeError, TypeError, ValueError, IndexError):
                                continue

                            if title and download_url:
                                items[mode].append((title, download_url, seeders, self._bytesizer(size)))

                except generic.HaltParseException:
                    pass
                except (StandardError, Exception):
                    logger.log(u'Failed to parse. Traceback: %s' % traceback.format_exc(), logger.ERROR)

                self._log_search(mode, len(items[mode]) - cnt, search_url)

            results = self._sort_seeding(mode, results + items[mode])

        return results

    def _episode_strings(self, ep_obj, **kwargs):
        return super(BTSceneProvider, self)._episode_strings(ep_obj, sep_date='.', **kwargs)

    def get_data(self, url):
        result = None
        resp = self.get_url(url, timeout=90)
        if self.should_skip():
            return result

        try:
            result = resp
            if re.search('(?i)\s+html', resp[0:30]):
                result = re.findall('(?i)"(magnet:[^"]+?)"', resp)[0]
        except IndexError:
            pass
        return result


provider = BTSceneProvider()
