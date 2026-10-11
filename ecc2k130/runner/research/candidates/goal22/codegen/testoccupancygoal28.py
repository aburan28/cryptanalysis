import unittest
from occupancy_goal28 import comparison

class PairedAcceptance(unittest.TestCase):
    def pairs(self,ratios):
        return [dict(ratio=r,samples={'2':{'rate':100.0},'3':{'rate':100*r}}) for r in ratios]
    def test_consistent_gain(self):
        row=comparison(self.pairs([1.03,1.04,1.02,1.03,1.04]))
        self.assertTrue(row['passesAcceptance']);self.assertGreater(row['pairedLogT95'][0],1)
    def test_no_gain_or_high_variance_rejected(self):
        for ratios in ([1]*5,[0.99]*5,[0.8,1.1,1.3,1.2,0.9]):
            self.assertFalse(comparison(self.pairs(ratios))['passesAcceptance'])
    def test_incomplete_pairs_rejected(self):
        with self.assertRaises(ValueError):comparison(self.pairs([1.1]*4))

if __name__=='__main__':unittest.main()
