"""Additional independent numeric/DescriptionVariables checks; no asset mutation."""
import unittest
import test_tooltip_presentation as p


class StockValues(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p.TooltipPresentation.setUpClass()

    def test_each_stock_rank_uses_official_numeric_values(self):
        source = p.TooltipPresentation
        official, _ = p.v.source(p.g, source.manifest, 'spell', 234)
        for entry in p.g.expanded_entries(source.manifest):
            base = entry['base_spell']
            for index in range(234):
                if not any(field <= index < field + 17 for field in (136, 153, 170, 187)):
                    self.assertEqual(source.client[base][index], official[base][index], (base, index))

    def test_variables_preserve_exact_rank_values_and_dynamic_expressions(self):
        manifest = p.TooltipPresentation.manifest
        spells, _ = p.v.source(p.g, manifest, 'spell', 234)
        stock, ss = p.v.source(p.g, manifest, 'variables', 2)
        rows, strings = p.g.load_dbc(p.ROOT / 'client_patch/staging/DBFilesClient/SpellDescriptionVariables.dbc', 2)
        actual = {r[0]: r for r in rows}
        for base, variable in manifest['stock_scoped_variables'].items():
            stock_id = spells[int(base)][232]
            original = p.g.read_string(ss, stock[stock_id][1])
            self.assertEqual(p.g.read_string(strings, actual[stock_id][1]), original)
            self.assertEqual(p.g.read_string(strings, actual[variable][1]), p.t.bind_stock_fields(original, int(base), definitions=True))


if __name__ == '__main__':
    unittest.main()
