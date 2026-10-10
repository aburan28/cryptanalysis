"""Integer-row combination table oracle, including failed budget prefixes."""
FIELDS = ('bits', 'groups', 'fallback_index_bytes', 'index_bytes', 'table_bytes',
          'peak_payload_bytes', 'pivot_updates', 'lookups', 'incomplete',
          'fallback_table_bytes', 'builds', 'combinations', 'copied_words',
          'table_word_xors', 'applications', 'applied_word_xors',
          'scalar_pivots_replaced', 'work')


class Tables:
    def __init__(self, stats, matrix, columns, width, cap, charge, emit):
        self.s, self.matrix = stats, matrix
        self.columns, self.width, self.cap = columns, width, cap
        self.charge, self.emit = charge, emit
        self.counts, self.tables = [], {}
        self.used = 0

    def pay(self, amount=1):
        self.charge(amount)
        self.s['work'] += amount

    def prepare(self):
        if not self.s['bits']:
            return
        self.pay()
        groups = (self.columns+3)//4
        self.s['groups'] = groups
        size = 5*groups
        if size > self.cap:
            self.s['fallback_index_bytes'] = 1
            return
        self.pay(2*groups)
        self.counts = [0]*groups
        self.used = size
        self.s['index_bytes'] = self.s['peak_payload_bytes'] = size

    def note(self, column):
        if not self.counts or self.counts[column//4] == 255:
            return
        self.pay()
        self.counts[column//4] += 1
        self.s['pivot_updates'] += 1

    def reduce(self, bits, proof, column, pivots):
        if not self.counts:
            return None
        self.pay()
        self.s['lookups'] += 1
        group = column//4
        start = group*4
        if self.counts[group] == 255:
            self.s['fallback_table_bytes'] += 1
            return None
        if self.counts[group] != 4 or start+4 > self.columns:
            self.s['incomplete'] += 1
            return None
        width = self.width-start//64
        if group not in self.tables:
            self.pay()
            size = 15*width*8+80
            if size > self.cap-self.used:
                self.counts[group] = 255
                self.s['fallback_table_bytes'] += 1
                return None
            self.pay(15*width+32)
            self.used += size
            self.s['table_bytes'] += size
            self.s['peak_payload_bytes'] = self.used
            entries, lookup = {}, {}
            for combination in range(1, 16):
                self.pay()
                bit = (combination & -combination).bit_length()-1
                previous = combination & (combination-1)
                value, source = pivots[start+bit]
                self.pay(width)
                if not previous:
                    self.s['copied_words'] += width
                else:
                    source = self.emit(['xor', entries[previous][1], source])
                    value ^= entries[previous][0]
                    self.s['table_word_xors'] += width
                    self.matrix['word_xors'] += width
                entries[combination] = value, source
                self.pay()
                signature = (value >> start) & 15
                assert signature and signature not in lookup
                lookup[signature] = combination
                self.s['combinations'] += 1
            self.tables[group] = entries, lookup
            self.s['builds'] += 1
        entries, lookup = self.tables[group]
        self.pay()
        combination = lookup[(bits >> start) & 15]
        value, source = entries[combination]
        self.pay(width)
        result = self.emit(['xor', proof, source])
        self.matrix['forward_xors'] += 1
        self.matrix['word_xors'] += width
        self.s['applications'] += 1
        self.s['applied_word_xors'] += width
        self.s['scalar_pivots_replaced'] += combination.bit_count()
        return bits ^ value, result
