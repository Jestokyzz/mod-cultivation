-- Reuse the actual WCollections companion window, not a look-alike dialog.
do
local entries = CultivationMentorSpellCatalog
local options = { ["Изучить: Ша"] = 2, ["Изучить: Небожители"] = 1 }
local active, side, option, selected, offset = false, nil, nil, 1, 0
local undo, rows, filtered = {}, {}, {}
local content, scanner, description, title, icon, list, scrollbar, search
local finish, refresh, describe
local function remember(fn) undo[#undo+1] = fn end
local function visibility(obj, shown)
    if not obj then return end
    local old = obj:IsShown()
    remember(function() if old then obj:Show() else obj:Hide() end end)
    if shown then obj:Show() else obj:Hide() end
end
local function script(obj, key, value)
    local old = obj:GetScript(key)
    remember(function() obj:SetScript(key, old) end)
    obj:SetScript(key, value)
end
local function settext(obj, value)
    local old = obj:GetText()
    remember(function() obj:SetText(old) end)
    obj:SetText(value)
end
local function gossipChoice()
    local values = {GetGossipOptions()}
    for i=1,#values,2 do
        if options[values[i]] then return (i+1)/2, options[values[i]] end
    end
end
finish = function(closeSession)
    if not active then return end
    active = false; option = nil
    content:Hide(); scanner:Hide()
    -- Restore children while their parent is hidden, before restoring lifecycle.
    CollectionsJournal:Hide()
    for i=#undo,1,-1 do undo[i]() end
    undo = {}
    if closeSession then CloseGossip() end
end
describe = function(index)
    if not active then return end
    selected = index
    local id = entries[index][side]
    local name, _, tex = GetSpellInfo(id)
    icon:SetTexture(tex); title:SetText(name or ("#"..id))
    scanner:SetOwner(UIParent,"ANCHOR_NONE"); scanner:ClearLines()
    scanner:SetHyperlink("spell:"..id)
    local text = {}
    -- Copy formatted native lines and colors, never display a nested tooltip.
    for i=2,scanner:NumLines() do
        for _,suffix in ipairs({"Left","Right"}) do
            local line = _G["CultivationMentorScannerText"..suffix..i]
            local value = line and line:GetText()
            if value and value~="" then
                local r,g,b = line:GetTextColor()
                text[#text+1] = string.format("|cff%02x%02x%02x",r*255,g*255,b*255)..value.."|r"
            end
        end
    end
    scanner:Hide()
    description:SetText(table.concat(text,"\n"))
    description:GetParent():SetHeight(math.max(1,description:GetStringHeight()+16))
    content.descriptionScroll:SetVerticalScroll(0)
end
refresh = function()
    if not active then return end
    local count = math.max(1,math.floor(list:GetHeight()/46))
    count = math.min(count,#rows)
    local maximum = math.max(0,#filtered-count)
    offset = math.max(0,math.min(maximum,offset))
    scrollbar:SetMinMaxValues(0,maximum)
    for i,row in ipairs(rows) do
        local index = i<=count and filtered[offset+i]
        if index then
            local name,_,tex = GetSpellInfo(entries[index][side])
            row.index=index; row.name:SetText(name or ("#"..entries[index][side]))
            row.icon:SetTexture(tex)
            if selected==index then row.selectedTexture:Show() else row.selectedTexture:Hide() end
            row:Show()
        else row:Hide() end
    end
end
local function filter()
    filtered={}; offset=0
    local needle=string.lower(search:GetText() or "")
    for i,pair in ipairs(entries) do
        local name=GetSpellInfo(pair[side]) or ""
        if needle=="" or string.find(string.lower(name),needle,1,true) then filtered[#filtered+1]=i end
    end
    scrollbar:SetValue(0); refresh()
end
local function create()
    content=CreateFrame("Frame","CultivationMentorContent",PetJournal)
    content:SetAllPoints(PetJournal); content:SetFrameLevel(PetJournal:GetFrameLevel()+10)
    content:Hide()
    list=CreateFrame("Frame",nil,content)
    list:SetPoint("TOPLEFT",PetJournal.LeftInset,"TOPLEFT",3,-36)
    list:SetPoint("BOTTOMRIGHT",PetJournal.LeftInset,"BOTTOMRIGHT",-2,5)
    scrollbar=CreateFrame("Slider","CultivationMentorListScrollBar",list,"HybridScrollBarTrimTemplate")
    scrollbar:SetScript("OnValueChanged",function(self,v) offset=math.floor(v+.5);refresh() end)
    scrollbar:SetPoint("TOPLEFT",list,"TOPRIGHT",4,20)
    scrollbar:SetPoint("BOTTOMLEFT",list,"BOTTOMRIGHT",4,11)
    scrollbar:SetValueStep(1); scrollbar:SetMinMaxValues(0,0); scrollbar:SetValue(0)
    scrollbar.trackBG:Show(); scrollbar.trackBG:SetVertexColor(0,0,0,.75)
    scrollbar.UpButton:SetScript("OnClick",function() scrollbar:SetValue(math.max(0,offset-1)) end)
    scrollbar.DownButton:SetScript("OnClick",function() scrollbar:SetValue(offset+1) end)
    list:EnableMouseWheel(true)
    list:SetScript("OnMouseWheel",function(self,d) scrollbar:SetValue(offset-d) end)
    for i=1,12 do
        local row=CreateFrame("Button","CultivationMentorSkill"..i,list,"PetListButtonTemplate")
        row:SetPoint("TOPLEFT",44,-(i-1)*46)
        -- Pet-only callbacks and adornments must not reach companion actions.
        for _,key in ipairs({"OnClick","OnDoubleClick","OnMouseDown","OnMouseUp","OnEnter","OnLeave","OnDragStart","OnReceiveDrag"}) do row:SetScript(key,nil) end
        for _,child in ipairs({row:GetChildren()}) do child:Hide();child:EnableMouse(false) end
        for _,key in ipairs({"petTypeIcon","SubscriptionOverlay","iconBorder","favorite","new","newGlow"}) do if row[key] then row[key]:Hide() end end
        row:SetScript("OnClick",function(self) describe(self.index);refresh() end)
        row:Hide(); rows[i]=row
    end
    search=CreateFrame("EditBox","CultivationMentorSearch",content,"SearchBoxTemplate")
    search:SetSize(235,20);search:SetPoint("TOPLEFT",PetJournal.LeftInset,"TOPLEFT",15,-9)
    search:SetAutoFocus(false);search:SetScript("OnTextChanged",function() if active then filter() end end)
    search:SetScript("OnEscapePressed",function(self) self:ClearFocus();finish(true) end)
    local display=PetJournal.PetDisplay
    icon=content:CreateTexture(nil,"ARTWORK");icon:SetSize(38,38)
    icon:SetPoint("TOPLEFT",display,"TOPLEFT",26,-29)
    title=content:CreateFontString(nil,"OVERLAY","GameFontHighlightLarge")
    title:SetPoint("LEFT",icon,"RIGHT",10,0);title:SetWidth(270);title:SetJustifyH("LEFT")
    local scroll=CreateFrame("ScrollFrame","CultivationMentorDescriptionScroll",content,"UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT",icon,"BOTTOMLEFT",0,-15)
    scroll:SetPoint("BOTTOMRIGHT",display,"BOTTOMRIGHT",-30,18)
    local child=CreateFrame("Frame",nil,scroll);child:SetSize(345,1);scroll:SetScrollChild(child)
    description=child:CreateFontString(nil,"OVERLAY","GameFontNormal")
    description:SetPoint("TOPLEFT");description:SetWidth(345);description:SetJustifyH("LEFT");description:SetJustifyV("TOP")
    content.descriptionScroll=scroll
    scanner=CreateFrame("GameTooltip","CultivationMentorScanner",UIParent,"GameTooltipTemplate");scanner:Hide()
end
local function open(found,chosen)
    if not CollectionsJournal or not PetJournal or not PetJournal.PetDisplay then return false end
    finish(false)
    if not content then create() end
    -- Hide a previous gossip panel without closing the new server session.
    local old=GossipFrame:GetScript("OnHide")
    GossipFrame:SetScript("OnHide",nil);HideUIPanel(GossipFrame);GossipFrame:SetScript("OnHide",old)
    HideUIPanel(CollectionsJournal)
    active=true;option=found;side=chosen;selected=1;offset=0
    script(CollectionsJournal,"OnShow",nil)
    script(PetJournal,"OnShow",nil);script(PetJournal,"OnHide",nil);script(PetJournal,"OnEvent",nil)
    script(CollectionsJournal,"OnHide",function() finish(true) end)
    for _,name in ipairs({"NewsJournal","MountJournal","AurasJournal","ToyBox","WardrobeCollectionFrame","CollectionsJournalPortraitButton","CollectionsJournalPortraitHelpBox","CollectionsJournalTransmogTabHelpBox"}) do visibility(_G[name],false) end
    for i=1,7 do visibility(_G["CollectionsJournalTab"..i],false) end
    visibility(PetJournal,true)
    for _,child in ipairs({PetJournal:GetChildren()}) do
        if child~=content and child~=PetJournal.LeftInset and child~=PetJournal.RightInset and child~=PetJournal.PetDisplay and child~=PetJournal.SummonButton then visibility(child,false) end
    end
    for _,child in ipairs({PetJournal.PetDisplay:GetChildren()}) do
        if child~=PetJournal.PetDisplay.ShadowOverlay then visibility(child,false) end
    end
    visibility(PetJournal.PetDisplay.NoPets,false);visibility(PetJournal.PetDisplay.NoPetsTex,false)
    visibility(PetJournal.PetDisplay.YesPetsTex,true);visibility(PetJournal.PetDisplay,true)
    settext(CollectionsJournalTitleText,side==2 and "Путь Ша" or "Путь Небожителей")
    local portrait=CollectionsJournalPortrait:GetTexture()
    remember(function() CollectionsJournalPortrait:SetTexture(portrait) end)
    SetPortraitToTexture(CollectionsJournalPortrait,side==2 and "Interface\\Icons\\sha_ability_rogue_envelopingshadows" or "Interface\\Icons\\achievement_faction_celestials")
    local accept=PetJournal.SummonButton
    local enabled=accept:IsEnabled();remember(function() if enabled==1 or enabled==true then accept:Enable() else accept:Disable() end end)
    settext(accept,"Изучить");visibility(accept,true);accept:Enable()
    script(accept,"OnClick",function(self)
        local current,path=gossipChoice()
        if not active or current~=option or path~=side then finish(true);return end
        self:Disable();SelectGossipOption(option)
    end)
    ShowUIPanel(CollectionsJournal);content:Show();search:SetText("")
    filter();describe(1)
    return true
end
local events=CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN");events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:SetScript("OnEvent",function(self,event)
    if event=="PLAYER_ENTERING_WORLD" then finish(false);return end
    -- Intercept the existing gossip receiver, so handler ordering cannot leave
    -- two windows or let stock OnHide prematurely end the mentor session.
    local native=GossipFrame:GetScript("OnEvent")
    GossipFrame:SetScript("OnEvent",function(self,event,...)
        if event=="GOSSIP_SHOW" then
            local found,chosen=gossipChoice()
            if found and open(found,chosen) then return end
            finish(false)
        elseif event=="GOSSIP_CLOSED" then finish(false) end
        if native then return native(self,event,...) end
    end)
end)
end
