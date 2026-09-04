-- Native FrameXML presentation for Cultivation / Rogue.  This file is loaded from the
-- single FrameXML-owner MPQ; it is not an AddOn and has no SavedVariables.
do
local labels = { celestial = "Небожитель", sha = "Ша" }
local colors = { celestial = "7CEBFF", sha = "C27CFF" }
local preparationPosition = "3:5:2"
local talentPositions = {
    ["1:9:2"] = true,
    ["1:11:2"] = true,
    ["1:5:2"] = true,
    ["2:5:2"] = true,
    ["2:7:2"] = true,
    ["2:11:2"] = true,
    ["2:3:2"] = true,
    ["3:5:4"] = true,
    ["3:9:2"] = true,
    ["3:11:2"] = true,
    ["3:5:2"] = true,
    ["3:7:2"] = true,
    ["3:3:2"] = true,
    ["1:7:2"] = true,
    ["1:6:2"] = true,
    ["1:9:1"] = true,
    ["2:8:3"] = true,
    ["3:7:3"] = true,
    ["3:9:1"] = true,
}

local function SetPathHeader(tooltip, path)
    local name = tooltip and tooltip.GetName and tooltip:GetName()
    local right = name and _G[name .. "TextRight1"]
    if not right or not labels[path] then return end
    right:SetText("|cff" .. colors[path] .. labels[path] .. "|r")
    right:Show()
end

local function HidePreparationActivationMetadata(tooltip)
    local name = tooltip and tooltip.GetName and tooltip:GetName()
    if not name then return end
    for line = 2, tooltip:NumLines() do
        local left = _G[name .. "TextLeft" .. line]
        local right = _G[name .. "TextRight" .. line]
        if left and left:GetText() == "Мгновенное действие" then
            left:SetText("")
            left:Hide()
        end
        local rightText = right and right:GetText()
        if rightText and string.find(rightText, "^Восстановление:") then
            right:SetText("")
            right:Hide()
        end
    end
end

local function PathFromRank(rank)
    if rank == labels.celestial then return "celestial" end
    if rank == labels.sha then return "sha" end
end

local function PathFromAuras()
    for index = 1, 40 do
        local name, rank, _, _, _, _, _, _, _, _, spellId = UnitBuff("player", index)
        if not name then break end
        if spellId == 86500 then return "celestial" end
        if spellId == 86501 then return "sha" end
        local path = PathFromRank(rank)
        if path then return path end
    end
end

local function PathFromSpellbook()
    if not GetNumSpellTabs or not GetSpellTabInfo or not GetSpellBookItemInfo then return end
    for tab = 1, GetNumSpellTabs() do
        local _, _, offset, count = GetSpellTabInfo(tab)
        for slot = offset + 1, offset + count do
            local _, spellId = GetSpellBookItemInfo(slot, BOOKTYPE_SPELL)
            if spellId then
                local _, rank = GetSpellInfo(spellId)
                local path = PathFromRank(rank)
                if path then return path end
            end
        end
    end
end

local function CurrentPath()
    local celestial = IsSpellKnown and IsSpellKnown(86500)
    local sha = IsSpellKnown and IsSpellKnown(86501)
    if celestial ~= sha then return celestial and "celestial" or "sha" end
    return PathFromAuras() or PathFromSpellbook()
end

local function PresentSpellHeader(tooltip)
    local _, rank = tooltip:GetSpell()
    local path = PathFromRank(rank)
    if path then
        SetPathHeader(tooltip, path)
        tooltip:Show()
    end
end

local function PresentTalentHeader(tooltip, tab, index, inspect, pet, group, preview)
    if inspect or pet or not tab or not index then return end
    local _, _, tier, column = GetTalentInfo(tab, index, inspect, pet, group, preview)
    local position = tostring(tab) .. ":" .. tostring(tier) .. ":" .. tostring(column)
    if not talentPositions[position] then return end
    local path = CurrentPath()
    if not path then return end
    if position == preparationPosition and path == "celestial" then
        HidePreparationActivationMetadata(tooltip)
    end
    SetPathHeader(tooltip, path)
    tooltip:Show()
end

for _, method in ipairs({ "SetSpell", "SetSpellBookItem", "SetAction", "SetHyperlink" }) do
    if type(GameTooltip[method]) == "function" then
        hooksecurefunc(GameTooltip, method, PresentSpellHeader)
    end
end

local talentHookInstalled
local function InstallTalentHook()
    if talentHookInstalled or not PlayerTalentFrame or type(GameTooltip.SetTalent) ~= "function" then return end
    hooksecurefunc(GameTooltip, "SetTalent", PresentTalentHeader)
    talentHookInstalled = true
end

local loader = CreateFrame("Frame")
loader:RegisterEvent("ADDON_LOADED")
loader:SetScript("OnEvent", function(self, event, name)
    if name == "Blizzard_TalentUI" then InstallTalentHook() end
end)
InstallTalentHook()
end
