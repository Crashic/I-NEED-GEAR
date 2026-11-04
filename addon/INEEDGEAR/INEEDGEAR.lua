local addonName = "INEEDGEAR"
INEEDGEARDB = INEEDGEARDB or { characters = {}, imported = {} }

-- ==========================================================
-- Окно
-- ==========================================================
local frame = CreateFrame("Frame", "INEEDGEARFrame", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
frame:SetSize(1000, 580)
frame:SetPoint("CENTER")
frame:SetMovable(true)
frame:EnableMouse(true)
frame:RegisterForDrag("LeftButton")
frame:SetScript("OnDragStart", frame.StartMoving)
frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
frame:SetFrameStrata("DIALOG")
frame:Hide()

frame:SetBackdrop({
    bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = true, tileSize = 16, edgeSize = 16,
    insets = { left = 4, right = 4, top = 4, bottom = 4 }
})
frame:SetBackdropColor(0.055, 0.045, 0.035, 0.97)
frame:SetBackdropBorderColor(0.55, 0.38, 0.18, 1)
table.insert(UISpecialFrames, "INEEDGEARFrame")

local logo = frame:CreateTexture(nil, "ARTWORK")
logo:SetSize(40, 40)
logo:SetPoint("TOPLEFT", 18, -13)
logo:SetTexture("Interface\\AddOns\\INEEDGEAR\\icon.tga")

local headerLine = frame:CreateTexture(nil, "ARTWORK")
headerLine:SetColorTexture(0.45, 0.31, 0.14, 1)
headerLine:SetPoint("TOPLEFT", 12, -66)
headerLine:SetPoint("TOPRIGHT", -12, -66)
headerLine:SetHeight(1)

local sidebar = frame:CreateTexture(nil, "BACKGROUND", nil, 1)
sidebar:SetColorTexture(0.11, 0.085, 0.06, 1)
sidebar:SetPoint("TOPLEFT", 8, -68)
sidebar:SetPoint("BOTTOMLEFT", 8, 8)
sidebar:SetWidth(192)

local sidebarLine = frame:CreateTexture(nil, "ARTWORK")
sidebarLine:SetColorTexture(0.45, 0.31, 0.14, 1)
sidebarLine:SetPoint("TOPLEFT", 202, -68)
sidebarLine:SetPoint("BOTTOMLEFT", 202, 12)
sidebarLine:SetWidth(1)

local title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
title:SetPoint("TOPLEFT", 72, -24)
title:SetTextColor(0.88, 0.73, 0.36)
title:SetText("I NEED GEAR")

local closeBtn = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
closeBtn:SetPoint("TOPRIGHT", -4, -4)

-- ==========================================================
-- Вкладки
-- ==========================================================
local tabs = {}
local activeTab = 1

local function ShowTab(index)
    for i, t in ipairs(tabs) do
        t.content:Hide()
        t.button:UnlockHighlight()
        t.button:SetNormalFontObject("GameFontNormal")
    end
    tabs[index].content:Show()
    tabs[index].button:LockHighlight()
    tabs[index].button:SetNormalFontObject("GameFontHighlight")
    activeTab = index
end

for i = 1, 3 do
    local btn = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    btn:SetID(i)
    btn:SetSize(172, 32)
    btn:SetPoint("TOPLEFT", 18, -96 - (i - 1) * 42)
    btn:SetScript("OnClick", function(self) ShowTab(self:GetID()) end)

    local content = CreateFrame("Frame", nil, frame)
    content:SetPoint("TOPLEFT", 218, -86)
    content:SetPoint("BOTTOMRIGHT", -14, 14)
    content:Hide()

    tabs[i] = { button = btn, content = content }
end

tabs[1].button:SetText("Мой персонаж")
tabs[2].button:SetText("Инсты")
tabs[3].button:SetText("Согильдийцы")
ShowTab(1)

-- ==========================================================
-- Вкладка 1: Мой персонаж
-- ==========================================================
local t1 = tabs[1].content

local function GetPlayerKey()
    local name = UnitFullName("player")
    local realm = GetRealmName()
    return name .. "-" .. realm
end

local saveGearBtn = CreateFrame("Button", nil, t1, "UIPanelButtonTemplate")
saveGearBtn:SetSize(220, 32)
saveGearBtn:SetPoint("TOPLEFT", 10, -10)
saveGearBtn:SetText("Сохранить и обновить")
saveGearBtn:SetScript("OnClick", function()
    local key = GetPlayerKey()
    INEEDGEARDB.characters[key] = INEEDGEARDB.characters[key] or {}
    INEEDGEARDB.characters[key].equipped = {}

    for slot = 0, 19 do
        local link = GetInventoryItemLink("player", slot)
        if link then
            table.insert(INEEDGEARDB.characters[key].equipped, link)
        end
    end
    print("|cff00ff00I NEED GEAR:|r Снаряжение сохранено. После загрузки интерфейса нажмите «Синхронизировать» в приложении.")
    ReloadUI()
end)

local exportBtn = CreateFrame("Button", nil, t1, "UIPanelButtonTemplate")
exportBtn:SetSize(220, 32)
exportBtn:SetPoint("TOPLEFT", 10, -90)
exportBtn:SetText("Показать код для обмена")
exportBtn:SetScript("OnClick", function()
    local key = GetPlayerKey()
    local data = INEEDGEARDB.characters[key]
    if not data or not data.equipped or #data.equipped == 0 then
        print("|cffff0000I NEED GEAR:|r Сначала сохраните снаряжение!")
        return
    end
    local out = key .. "||"
    for _, link in ipairs(data.equipped) do
        local itemString = link:match("|H(.*)|h")
        if itemString then
            out = out .. itemString .. "|"
        end
    end
    print("|cff00ff00I NEED GEAR код:|r")
    print(out)
    print("|cffffd700Скопируйте строку выше и отправьте другому игроку.|r")
end)

local importBtn = CreateFrame("Button", nil, t1, "UIPanelButtonTemplate")
importBtn:SetSize(220, 32)
importBtn:SetPoint("TOPLEFT", 10, -50)
importBtn:SetText("Обновить данные друзей")
importBtn:SetScript("OnClick", function() ReloadUI() end)

local info1 = t1:CreateFontString(nil, "OVERLAY", "GameFontNormal")
info1:SetPoint("TOPLEFT", 10, -140)
info1:SetJustifyH("LEFT")
info1:SetText("1) Нажми «Сохранить и обновить». Интерфейс перезагрузится.\n" ..
              "2) В приложении на ПК нажми «Синхронизировать».\n" ..
              "3) Нажми здесь «Обновить данные друзей».\n" ..
              "4) Открой вкладку «Согильдийцы». Игру закрывать не нужно.")

-- ==========================================================
-- Вкладка 2: Инсты (заглушка)
-- ==========================================================
local t2 = tabs[2].content
local info2 = t2:CreateFontString(nil, "OVERLAY", "GameFontNormal")
info2:SetPoint("TOPLEFT", 10, -10)
info2:SetJustifyH("LEFT")
info2:SetText("Здесь будет список предметов из подземелий.\n" ..
              "Каждый предмет можно пометить как «Нужно» или «Не отказался бы».\n\n" ..
              "(Раздел будет дополнен в следующей версии.)")

-- ==========================================================
-- Вкладка 3: Согильдийцы
-- ==========================================================
local t3 = tabs[3].content

local scrollFrame = CreateFrame("ScrollFrame", "INEEDGEARListScroll", t3, "UIPanelScrollFrameTemplate")
scrollFrame:SetPoint("TOPLEFT", 10, -10)
scrollFrame:SetSize(220, 380)

local listContent = CreateFrame("Frame", nil, scrollFrame)
listContent:SetSize(220, 1)
scrollFrame:SetScrollChild(listContent)

local detailBox = CreateFrame("Frame", nil, t3, "BackdropTemplate")
detailBox:SetPoint("TOPLEFT", scrollFrame, "TOPRIGHT", 14, 0)
detailBox:SetSize(440, 380)
detailBox:SetBackdrop({
    bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = true, tileSize = 16, edgeSize = 16,
    insets = { left = 4, right = 4, top = 4, bottom = 4 }
})
detailBox:SetBackdropColor(0.06, 0.05, 0.04, 0.9)
detailBox:SetBackdropBorderColor(0.55, 0.38, 0.18, 1)

local detailText = detailBox:CreateFontString(nil, "OVERLAY", "GameFontNormal")
detailText:SetPoint("TOPLEFT", 8, -8)
detailText:SetJustifyH("LEFT")
detailText:SetWidth(420)
detailText:SetText("Выбери персонажа слева.")

local function ShowCharacterDetail(displayName, rawLua)
    local items = {}
    for itemString in rawLua:gmatch("|H([^|]+)|h") do
        table.insert(items, itemString)
    end

    local out = "|cff00ff00" .. displayName .. "|r\n\n"
    if #items == 0 then
        out = out .. "Нет данных о снаряжении."
    else
        for _, it in ipairs(items) do
            out = out .. "• " .. it .. "\n"
        end
    end
    detailText:SetText(out)
end

local function RebuildList()
    for _, child in ipairs({listContent:GetChildren()}) do
        child:Hide()
        child:SetParent(nil)
    end

    local imported = INEEDGEAR_IMPORTED or {}
    local y = 0
    for name, rawLua in pairs(imported) do
        local btn = CreateFrame("Button", nil, listContent, "UIPanelButtonTemplate")
        btn:SetSize(200, 26)
        btn:SetPoint("TOPLEFT", 0, -y)
        btn:SetText(name)
        btn:SetScript("OnClick", function() ShowCharacterDetail(name, rawLua) end)
        y = y + 28
    end
    listContent:SetHeight(math.max(1, y))
end

-- ==========================================================
-- Слэш-команды
-- ==========================================================
SLASH_INEEDGEAR1 = "/ing"
SLASH_INEEDGEAR2 = "/ineedgear"
SlashCmdList["INEEDGEAR"] = function()
    if frame:IsShown() then
        frame:Hide()
    else
        RebuildList()
        frame:Show()
    end
end

-- Кнопка открытия у миникарты; положение сохраняется вместе с настройками аддона.
local minimapBtn = CreateFrame("Button", "INEEDGEARMinimapButton", Minimap)
minimapBtn:SetSize(32, 32)
minimapBtn:SetFrameStrata("MEDIUM")
minimapBtn:SetNormalTexture("Interface\\AddOns\\INEEDGEAR\\icon.tga")
minimapBtn:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square", "ADD")
minimapBtn:RegisterForClicks("LeftButtonUp")
minimapBtn:RegisterForDrag("LeftButton")
local function PositionMinimapButton()
    local angle = math.rad(tonumber(INEEDGEARDB.minimapAngle) or 225)
    minimapBtn:ClearAllPoints()
    minimapBtn:SetPoint("CENTER", Minimap, "CENTER", math.cos(angle) * 82, math.sin(angle) * 82)
end
minimapBtn:SetScript("OnClick", function() SlashCmdList["INEEDGEAR"]() end)
minimapBtn:SetScript("OnDragStart", function(self)
    self:SetScript("OnUpdate", function()
        local x, y = GetCursorPosition()
        local scale = Minimap:GetEffectiveScale()
        local centerX, centerY = Minimap:GetCenter()
        INEEDGEARDB.minimapAngle = math.deg(math.atan2(y / scale - centerY, x / scale - centerX))
        PositionMinimapButton()
    end)
end)
minimapBtn:SetScript("OnDragStop", function(self) self:SetScript("OnUpdate", nil) end)
minimapBtn:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("I NEED GEAR", 1, 0.82, 0)
    GameTooltip:AddLine("Нажмите, чтобы открыть аддон.", 1, 1, 1)
    GameTooltip:AddLine("Перетащите значок вдоль миникарты.", 0.7, 0.7, 0.7)
    GameTooltip:Show()
end)
minimapBtn:SetScript("OnLeave", function() GameTooltip:Hide() end)
PositionMinimapButton()

-- ==========================================================
-- Загрузка
-- ==========================================================
local ef = CreateFrame("Frame")
ef:RegisterEvent("ADDON_LOADED")
ef:SetScript("OnEvent", function(_, _, name)
    if name == addonName then
        INEEDGEARDB = INEEDGEARDB or { characters = {}, imported = {} }
        INEEDGEARDB.characters = INEEDGEARDB.characters or {}
        INEEDGEARDB.imported = nil
        PositionMinimapButton()
        print("|cff00ff00I NEED GEAR|r загружен. /ing — открыть.")
    end
end)
