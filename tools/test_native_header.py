"""Run actual FrameXML header in Lua 5.1. Does not constitute game GUI acceptance."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, r'C:\Solo WotLK\work\rogue-paths-schema3-deps')
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
STUB = r'''
Known = {[86501] = true}
Tier, Column, Rank, Tab = 5, 2, 0, 3
local function label()
    return { text = "", SetText = function(self, text) self.text = text end,
        GetText = function(self) return self.text end, Show = function() end, Hide = function() end }
end
for i = 1, 8 do
    _G['GameTooltipTextLeft' .. i] = label()
    _G['GameTooltipTextRight' .. i] = label()
end
GameTooltip = { GetName = function() return 'GameTooltip' end, NumLines = function() return 8 end,
    GetSpell = function() return 'Test', 'Ша', 86307 end, Show = function() end }
NativeCost, NativeCD = 'Энергия: 40', 'Восстановление: 8 мин.'
function NativeTooltip()
    GameTooltipTextLeft1:SetText('Native title')
    GameTooltipTextLeft2:SetText(NativeCost)
    GameTooltipTextLeft3:SetText('Мгновенное действие')
    GameTooltipTextRight3:SetText(NativeCD)
    GameTooltipTextLeft4:SetText('NATIVE DBC BODY')
end
for _, method in ipairs({'SetTalent','SetSpell','SetSpellBookItem','SetAction','SetHyperlink'}) do
    GameTooltip[method] = NativeTooltip
end
function hooksecurefunc(object, key, hook)
    local native = object[key]
    object[key] = function(...) native(...); hook(...) end
end
function IsSpellKnown(id) return Known[id] or false end
function GetTalentInfo() return 'talent', '', Tier, Column, Rank, 1 end
function GetSpellInfo() error('Unknown custom spell must not be queried') end
function UnitBuff() return nil end
function GetLocale() return 'ruRU' end
function CreateFrame()
    Loader = { RegisterEvent = function() end, SetScript = function(self, key, callback) self[key] = callback end }
    return Loader
end
function CreateTalentFrame()
    PlayerTalentFrame = { HookScript = function(self, key, callback) self[key] = callback end }
    PlayerTalentFrameTalent1 = { handler = function() NativeTooltip() end, GetID = function() return 1 end,
        GetScript = function(self) return self.handler end, SetScript = function(self, key, fn) self.handler = fn end }
end
function PanelTemplates_GetSelectedTab() return Tab end
function Plain(text) return string.gsub(string.gsub(text, '|c%x%x%x%x%x%x%x%x', ''), '|r', '') end
'''


class NativeHeader(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(STUB)
        self.lua.execute((ROOT / 'client_patch/framexml/CultivationRogueHeader.lua').read_text('utf8'))
        self.lua.execute("CreateTalentFrame(); Loader.OnEvent(Loader, 'ADDON_LOADED', 'Blizzard_TalentUI')")

    def value(self, expression):
        return self.lua.eval('(' + expression + ')')

    def test_initial_sha_preparation_no_spell_cache(self):
        self.lua.execute('GameTooltip:SetTalent(3, 1)')
        self.assertEqual(self.value('Plain(GameTooltipTextRight3.text)'), 'Восстановление: 390 сек.')
        self.assertEqual(self.value('GameTooltipTextLeft4.text'), 'NATIVE DBC BODY')

    def test_both_paths_reset_and_preparation_affects_step(self):
        self.lua.execute('Known = {[86500]=true}; Tier=9; Column=2; NativeCD="Восстановление: 30 сек."')
        for learned, expected in ((False, '30'), (True, '21'), (False, '30')):
            self.lua.execute('Known[86107] = ' + str(learned).lower() + '; GameTooltip:SetTalent(3,1)')
            self.assertEqual(self.value('Plain(GameTooltipTextRight3.text)'), f'Восстановление: {expected} сек.')

    def test_initial_sha_ghostly_cost_and_cd(self):
        self.lua.execute('Tier=3; Column=2; GameTooltip:SetTalent(3,1)')
        self.assertEqual(self.value('Plain(GameTooltipTextLeft2.text)'), 'Энергия: 25')
        self.assertEqual(self.value('Plain(GameTooltipTextRight3.text)'), 'Восстановление: 15 сек.')

    def test_button_bypasses_settalent_and_replaced_handler(self):
        self.lua.execute('GameTooltip.SetTalent = NativeTooltip; PlayerTalentFrameTalent1:handler()')
        self.assertEqual(self.value('Plain(GameTooltipTextRight3.text)'), 'Восстановление: 390 сек.')
        self.lua.execute('PlayerTalentFrameTalent1.handler = NativeTooltip; PlayerTalentFrame:OnShow(); PlayerTalentFrameTalent1:handler()')
        self.assertEqual(self.value('Plain(GameTooltipTextRight3.text)'), 'Восстановление: 390 сек.')

    def test_celestial_preparation_hides_activation_metadata(self):
        self.lua.execute('Known = {[86500]=true}; GameTooltip:SetTalent(3,1)')
        self.assertEqual(self.value('GameTooltipTextLeft3.text'), '')
        self.assertEqual(self.value('GameTooltipTextRight3.text'), '')
        self.assertEqual(self.value('GameTooltipTextLeft4.text'), 'NATIVE DBC BODY')


if __name__ == '__main__':
    unittest.main(verbosity=2)
