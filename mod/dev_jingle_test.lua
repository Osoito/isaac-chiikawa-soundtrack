-- DEV ONLY. Excluded from release builds by `build/deploy.py --release`.
--
-- Most jingles fire in situations that are tedious to reproduce (a devil room door
-- appearing, a specific boss dying), so auditioning them by playing the game is not
-- viable. These console commands trigger them directly through the same call
-- Soundtrack Menu itself uses, MusicManager():PlayJingle.
--
--   chiikawa_check          verify all 85 track names resolve to a real music id
--   chiikawa_jingle 27      play the jingle in slot 27
--   chiikawa_jingle all     walk all 22 jingles, 3 seconds apart
--   chiikawa_jingle stop    cancel a walk in progress
--   chiikawa_music 36       play a looping track, e.g. to compare jingle loudness

local dev = RegisterMod("Chiikawa Soundtrack Dev", 1)
local slots = include("dev_slots")

local WALK_INTERVAL = 180 -- render frames; roughly 3 seconds
local LABEL_FRAMES = 120

local walk = nil
local walkIndex = 0
local frames = 0
local nextAt = 0
local label = nil
local labelUntil = 0

local function say(fmt, ...)
    Isaac.ConsoleOutput(string.format(fmt, ...) .. "\n")
end

local function musicId(slot)
    local name = slots.names[slot]
    if not name then return nil, nil end
    return Isaac.GetMusicIdByName(slots.soundtrack .. " " .. name), name
end

local function playJingle(slot)
    local id, name = musicId(slot)
    if not name then
        say("no such slot: %s", tostring(slot))
        return false
    end
    if not id or id <= 0 then
        say("MISSING [%d] %s %s -- GetMusicIdByName returned %s",
            slot, slots.soundtrack, name, tostring(id))
        return false
    end
    MusicManager():PlayJingle(id)
    say("[%d] %s -- music id %d", slot, name, id)
    label = string.format("[%d] %s", slot, name)
    labelUntil = frames + LABEL_FRAMES
    return true
end

local function check()
    local missing = 0
    for slot = 1, slots.count do
        local id, name = musicId(slot)
        if not id or id <= 0 then
            missing = missing + 1
            say("MISSING [%d] %s %s", slot, slots.soundtrack, name)
        end
    end
    if missing == 0 then
        say("OK: all %d Chiikawa tracks resolve", slots.count)
    else
        say("%d of %d tracks missing -- those slots fall back to vanilla Rebirth music",
            missing, slots.count)
    end
end

dev:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, cmd, args)
    cmd = string.lower(cmd or "")
    args = string.lower(args or "")

    if cmd == "chiikawa_check" then
        check()
    elseif cmd == "chiikawa_jingle" then
        if args == "all" then
            walk, walkIndex, nextAt = slots.jingles, 0, frames
            say("walking %d jingles, %s to cancel", #slots.jingles, "chiikawa_jingle stop")
        elseif args == "stop" then
            walk = nil
            say("stopped")
        else
            local n = math.floor(tonumber(args) or -1)
            if n > 0 then playJingle(n) else say("usage: chiikawa_jingle <slot|all|stop>") end
        end
    elseif cmd == "chiikawa_music" then
        local n = math.floor(tonumber(args) or -1)
        local id, name = musicId(n)
        if id and id > 0 then
            MusicManager():Play(id, 0)
            say("[%d] %s -- music id %d (looping)", n, name, id)
        else
            say("usage: chiikawa_music <slot 1-%d>", slots.count)
        end
    end
end)

dev:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    frames = frames + 1

    if walk and frames >= nextAt then
        walkIndex = walkIndex + 1
        if walkIndex > #walk then
            walk = nil
            say("done")
        else
            playJingle(walk[walkIndex])
            nextAt = frames + WALK_INTERVAL
        end
    end

    if label and frames < labelUntil then
        Isaac.RenderText(label, 60, 40, 1, 1, 1, 1)
    end
end)

-- main.lua loads this through pcall, which swallows load errors so a release build
-- (where this file is absent) stays quiet. This line is the positive signal: if you
-- deployed a dev build and do not see it, the harness failed to load.
say("Chiikawa dev harness ready -- chiikawa_check | chiikawa_jingle all | chiikawa_music <slot>")
