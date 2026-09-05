-- Native FrameXML presentation for Cultivation / Rogue.  This file is loaded from the
-- single FrameXML-owner MPQ; it is not an AddOn and has no SavedVariables.
do
local labels = { celestial = "Небожитель", sha = "Ша" }
local colors = { celestial = "7CEBFF", sha = "C27CFF" }
local preparationPosition = "3:5:2"
-- BEGIN GENERATED TALENT METADATA
local talentMetadata = {
    ["1:9:2"] = {
        celestial = { { cost = 60, cooldown = 0, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 60, cooldown = 0, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["1:11:2"] = {
        celestial = { { cost = 0, cooldown = 0, passive = false, costChanged = true, cooldownChanged = false, preparation = false } },
        sha = { { cost = 30, cooldown = 30000, passive = false, costChanged = true, cooldownChanged = true, preparation = false } },
    },
    ["1:5:2"] = {
        celestial = { { cost = 0, cooldown = 180000, passive = false, costChanged = false, cooldownChanged = false, preparation = true } },
        sha = { { cost = 0, cooldown = 180000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["2:5:2"] = {
        celestial = { { cost = 25, cooldown = 120000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 25, cooldown = 120000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["2:7:2"] = {
        celestial = { { cost = 0, cooldown = 180000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 180000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["2:11:2"] = {
        celestial = { { cost = 0, cooldown = 90000, passive = false, costChanged = false, cooldownChanged = true, preparation = false } },
        sha = { { cost = 0, cooldown = 120000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["2:3:2"] = {
        celestial = { { cost = 10, cooldown = 6000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 10, cooldown = 6000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["3:5:4"] = {
        celestial = { { cost = 35, cooldown = 0, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 35, cooldown = 0, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["3:9:2"] = {
        celestial = { { cost = 0, cooldown = 30000, passive = false, costChanged = true, cooldownChanged = false, preparation = true } },
        sha = { { cost = 20, cooldown = 30000, passive = false, costChanged = true, cooldownChanged = false, preparation = false } },
    },
    ["3:11:2"] = {
        celestial = { { cost = 0, cooldown = 60000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 60000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["3:5:2"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = true, preparation = false } },
        sha = { { cost = 0, cooldown = 390000, passive = false, costChanged = false, cooldownChanged = true, preparation = false } },
    },
    ["3:7:2"] = {
        celestial = { { cost = 0, cooldown = 20000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 20000, passive = false, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["3:3:2"] = {
        celestial = { { cost = 30, cooldown = 20000, passive = false, costChanged = true, cooldownChanged = false, preparation = false } },
        sha = { { cost = 25, cooldown = 15000, passive = false, costChanged = true, cooldownChanged = true, preparation = false } },
    },
    ["1:7:2"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["1:6:2"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["1:9:1"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["2:8:3"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["3:7:3"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
    },
    ["3:9:1"] = {
        celestial = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
        sha = { { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false }, { cost = 0, cooldown = 0, passive = true, costChanged = false, cooldownChanged = false, preparation = false } },
    },
}
-- END GENERATED TALENT METADATA
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
    local _, _, tier, column, rank = GetTalentInfo(tab, index, inspect, pet, group, preview)
    local position = tostring(tab) .. ":" .. tostring(tier) .. ":" .. tostring(column)
    if not talentPositions[position] then return end
    local path = CurrentPath()
    if not path then return end
    if position == preparationPosition and path == "celestial" then
        HidePreparationActivationMetadata(tooltip)
    else
        -- No unknown-spell scans: even rank 0 resolves the generated final row.
        -- Description remains native DBC; this corrects only stock-derived headers.
        local ranks = talentMetadata[position] and talentMetadata[position][path]
        local data = ranks and ranks[math.max(1, math.min(rank or 0, #ranks))]
        local name = tooltip:GetName()
        if data and not data.passive and name then
            local cooldown = data.cooldown
            local cooldownChanged = data.cooldownChanged
            if data.preparation and IsSpellKnown and IsSpellKnown(86107) then
                cooldown = cooldown * 0.7
                cooldownChanged = true
            end
            local russian = not GetLocale or GetLocale() == "ruRU"
            local costPrefix = russian and "Энергия: " or "Energy: "
            local cdPrefix = russian and "Восстановление: " or "Cooldown: "
            local seconds = cooldown / 1000
            local formatted = (seconds % 60 == 0) and
                (tostring(seconds / 60) .. (russian and " мин." or " min")) or
                (tostring(seconds) .. (russian and " сек." or " sec"))
            local costText = data.costChanged and ("|cff" .. colors[path] .. data.cost .. "|r") or tostring(data.cost)
            local cdText = cooldownChanged and ("|cff" .. colors[path] .. formatted .. "|r") or formatted
            for line = 2, tooltip:NumLines() do
                for _, side in ipairs({ "Left", "Right" }) do
                    local label = _G[name .. "Text" .. side .. line]
                    local text = label and label:GetText()
                    if text then
                        local plain = string.gsub(string.gsub(text, "|c%x%x%x%x%x%x%x%x", ""), "|r", "")
                        if string.sub(plain, 1, #costPrefix) == costPrefix then
                            label:SetText(data.cost > 0 and
                                (costPrefix .. costText) or "")
                        elseif string.sub(plain, 1, #cdPrefix) == cdPrefix then
                            label:SetText(cooldown > 0 and
                                (cdPrefix .. cdText) or "")
                        end
                    end
                end
            end
        end
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
local buttonWrappers = {}
local function InstallButtonHeaders()
    for index = 1, 40 do
        local button = _G["PlayerTalentFrameTalent" .. index]
        if button and button.GetScript and button.SetScript then
            local native = button:GetScript("OnEnter")
            if native ~= buttonWrappers[button] then
                local wrapper = function(self, ...)
                    if native then native(self, ...) end
                    local frame = PlayerTalentFrame
                    if frame and PanelTemplates_GetSelectedTab then
                        PresentTalentHeader(GameTooltip, PanelTemplates_GetSelectedTab(frame), self:GetID(),
                            frame.inspect, frame.pet, frame.talentGroup)
                    end
                end
                button:SetScript("OnEnter", wrapper)
                buttonWrappers[button] = wrapper
            end
        end
    end
end
local function InstallTalentHook()
    if not PlayerTalentFrame or type(GameTooltip.SetTalent) ~= "function" then return end
    InstallButtonHeaders()
    if talentHookInstalled then return end
    hooksecurefunc(GameTooltip, "SetTalent", PresentTalentHeader)
    if PlayerTalentFrame.HookScript then
        PlayerTalentFrame:HookScript("OnShow", InstallButtonHeaders)
    end
    talentHookInstalled = true
end

local loader = CreateFrame("Frame")
loader:RegisterEvent("ADDON_LOADED")
loader:SetScript("OnEvent", function(self, event, name)
    if name == "Blizzard_TalentUI" then InstallTalentHook() end
end)
InstallTalentHook()
end
