local addonName = "INEEDGEAR"
INEEDGEARDB = INEEDGEARDB or { characters = {}, imported = {} }

-- ==========================================================
-- Окно
-- ==========================================================
local frame = CreateFrame("Frame", "INEEDGEARFrame", UIParent)
frame:SetSize(720, 500)
frame:SetPoint("CENTER")
frame:SetMovable(true)
frame:EnableMouse(true)
frame:RegisterForDrag("LeftButton")
frame:SetScript("OnDragStart", frame.StartMoving)
frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
frame:SetFrameStrata("DIALOG")
frame:Hide()

frame:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true, tileSize = 32, edgeSize = 32,
    insets = { left = 8, right = 8, top = 8, bottom = 8 }
})

local title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
title:SetPoint("TOP", 0, -16)
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
    end
    tabs[index].content:Show()
    tabs[index].button:LockHighlight()
    activeTab = index
end

for i = 1, 3 do
    local btn = CreateFrame("Button", nil, frame, "CharacterFrameTabButtonTemplate")
    btn:SetID(i)
    btn:SetPoint("TOPLEFT", 20 + (i - 1) * 120, -42)
    btn:SetScript("OnClick", function(self) ShowTab(self:GetID()) end)

    local content = CreateFrame("Frame", nil, frame)
    content:SetPoint("TOPLEFT", 14, -76)
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
saveGearBtn:SetText("Сохранить снаряжение")
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
    print("|cff00ff00I NEED GEAR:|r Снаряжение сохранено ("..#INEEDGEARDB.characters[key].equipped.." предметов)")
end)

local exportBtn = CreateFrame("Button", nil, t1, "UIPanelButtonTemplate")
exportBtn:SetSize(220, 32)
exportBtn:SetPoint("TOPLEFT", 10, -50)
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

local info1 = t1:CreateFontString(nil, "OVERLAY", "GameFontNormal")
info1:SetPoint("TOPLEFT", 10, -100)
info1:SetJustifyH("LEFT")
info1:SetText("1) Нажми «Сохранить снаряжение».\n" ..
              "2) Выйди из игры.\n" ..
              "3) Запусти приложение на ПК и нажми «Обновить».\n" ..
              "4) Данные друзей появятся на вкладке «Согильдийцы».")

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
detailBox:SetBackdropColor(0, 0, 0, 0.4)

local detailText = detailBox:CreateFontString(nil, "OVERLAY", "GameFontNormal")
detailText:SetPoint("TOPLEFT", 8, -8)
detailText:SetJustifyH("LEFT")
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

    local imported = INEEDGEARDB.imported or {}
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

-- ==========================================================
-- Загрузка
-- ==========================================================
local ef = CreateFrame("Frame")
ef:RegisterEvent("ADDON_LOADED")
ef:SetScript("OnEvent", function(_, _, name)
    if name == addonName then
        INEEDGEARDB = INEEDGEARDB or { characters = {}, imported = {} }
        INEEDGEARDB.characters = INEEDGEARDB.characters or {}
        INEEDGEARDB.imported = INEEDGEARDB.imported or {}
        print("|cff00ff00I NEED GEAR|r загружен. /ing — открыть.")
    end
end)
