local mod = RegisterMod("Chiikawa Soundtrack", 1)

function mod:onGameStart()
    if SoundtrackSongList then
        AddSoundtrackToMenu("Chiikawa")
    else
        Isaac.ConsoleOutput("The Soundtrack Menu mod is required for the Chiikawa Soundtrack\n")
    end
end

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, mod.onGameStart)

-- Development helpers. Absent from release builds, so failure to load is expected.
pcall(include, "dev_jingle_test")
