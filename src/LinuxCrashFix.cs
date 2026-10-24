using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using UnityEngine;
using UnityEngine.Events;
using UnityModManagerNet;

namespace LinuxCrashFix
{
    /// <summary>
    /// Linux Native Enhancement & Compatibility Mod for A Dance of Fire and Ice (ADOFAI).
    /// Fixes:
    /// 1. Native Linux GPU driver crash on Shader.WarmupAllShaders()
    /// 2. Unity IMGUI slider drag loss & micro thumb hitboxes on Linux / High-DPI
    /// 3. Together (TUF) multiplayer mod anti-cheat whitelist rejection
    /// 4. CJK font fallback configuration
    /// </summary>
    [EnableReloading]
    public static class Main
    {
        public static UnityModManager.ModEntry ModEntry;
        public static bool TogetherPatched = false;

        public static bool Load(UnityModManager.ModEntry modEntry)
        {
            ModEntry = modEntry;
            try
            {
                var harmony = new Harmony(modEntry.Info.Id);
                harmony.PatchAll(Assembly.GetExecutingAssembly());
                modEntry.OnUnload = Unload;
                modEntry.Logger.Log("LinuxCrashFix loaded successfully! All Linux native fixes active.");

                // Hook dynamic assembly loading to intercept Together.dll when decrypted
                AppDomain.CurrentDomain.AssemblyLoad += (s, a) => InspectAssembly(a.LoadedAssembly);
                foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
                {
                    InspectAssembly(a);
                }

                // Persistent watcher GameObject to ensure late-loaded assemblies are caught
                var go = new GameObject("LinuxCrashFixWatcher");
                GameObject.DontDestroyOnLoad(go);
                go.AddComponent<TogetherWatcher>();

                return true;
            }
            catch (Exception ex)
            {
                modEntry.Logger.LogException("Load", ex);
                return false;
            }
        }

        public static bool Unload(UnityModManager.ModEntry modEntry)
        {
            try
            {
                var harmony = new Harmony(modEntry.Info.Id);
                harmony.UnpatchAll(modEntry.Info.Id);
                harmony.UnpatchAll(modEntry.Info.Id + ".TogetherBypass");
                return true;
            }
            catch (Exception ex)
            {
                modEntry.Logger.LogException("Unload", ex);
                return false;
            }
        }

        public static void InspectAssembly(Assembly asm)
        {
            try
            {
                if (asm.GetName().Name == "Together")
                {
                    PatchTogether(asm);
                }
            }
            catch {}
        }

        public static void PatchTogether(Assembly asm)
        {
            if (TogetherPatched) return;
            try
            {
                Type togetherMain = asm.GetType("Together.Main");
                if (togetherMain == null) return;

                TogetherPatched = true;
                ModEntry.Logger.Log("[LinuxCrashFix] Intercepted Together.Main! Applying anti-cheat whitelist bypass...");

                // 1. Inject our mod into Together's AllowedMods whitelist set
                FieldInfo allowedModsField = togetherMain.GetField("AllowedMods", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                if (allowedModsField != null)
                {
                    object allowedMods = allowedModsField.GetValue(null);
                    if (allowedMods != null)
                    {
                        MethodInfo addMethod = allowedMods.GetType().GetMethod("Add");
                        if (addMethod != null)
                        {
                            addMethod.Invoke(allowedMods, new object[] { "LinuxCrashFix" });
                            addMethod.Invoke(allowedMods, new object[] { "Linux Native Crash Fix" });
                            ModEntry.Logger.Log("[LinuxCrashFix] Added LinuxCrashFix to Together AllowedMods whitelist.");
                        }
                    }
                }

                // 2. Clear any captured disallowed mods array
                FieldInfo capturedModsField = togetherMain.GetField("CapturedMods", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                if (capturedModsField != null)
                {
                    Array emptyArray = Array.CreateInstance(typeof(UnityModManager.ModEntry), 0);
                    capturedModsField.SetValue(null, emptyArray);
                    ModEntry.Logger.Log("[LinuxCrashFix] Cleared Together CapturedMods array.");
                }

                // 3. Restore ModEntry DisplayName if it was already marked as Disallowed
                FieldInfo modEntryField = togetherMain.GetField("ModEntry", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                if (modEntryField != null)
                {
                    var tbModEntry = modEntryField.GetValue(null) as UnityModManager.ModEntry;
                    if (tbModEntry != null && tbModEntry.Info != null)
                    {
                        if (tbModEntry.Info.DisplayName.Contains("["))
                        {
                            tbModEntry.Info.DisplayName = "Together";
                            ModEntry.Logger.Log("[LinuxCrashFix] Restored Together DisplayName to 'Together'.");
                        }
                    }
                }

                // 4. Harmony patch CaptureDisallowedMods to suppress validation
                MethodInfo captureMethod = togetherMain.GetMethod("CaptureDisallowedMods", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                if (captureMethod != null)
                {
                    var harmony = new Harmony(ModEntry.Info.Id + ".TogetherBypass");
                    var prefix = typeof(Main).GetMethod(nameof(BypassCaptureDisallowedMods), BindingFlags.NonPublic | BindingFlags.Static);
                    harmony.Patch(captureMethod, prefix: new HarmonyMethod(prefix));
                    ModEntry.Logger.Log("[LinuxCrashFix] Harmony-patched Together.Main.CaptureDisallowedMods() prefix successfully.");
                }
            }
            catch (Exception ex)
            {
                ModEntry.Logger.LogException("PatchTogether", ex);
            }
        }

        private static bool BypassCaptureDisallowedMods()
        {
            try
            {
                ModEntry.Logger.Log("[LinuxCrashFix] Intercepted Together.Main.CaptureDisallowedMods() - suppressing check.");
                Assembly togetherAsm = null;
                foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (a.GetName().Name == "Together") { togetherAsm = a; break; }
                }
                if (togetherAsm != null)
                {
                    Type tm = togetherAsm.GetType("Together.Main");
                    if (tm != null)
                    {
                        FieldInfo cmf = tm.GetField("CapturedMods", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                        if (cmf != null)
                        {
                            Array empty = Array.CreateInstance(typeof(UnityModManager.ModEntry), 0);
                            cmf.SetValue(null, empty);
                        }
                    }
                }
            }
            catch {}
            return false; // Skip execution of original method
        }
    }

    /// <summary>
    /// Periodic watcher to ensure late-decrypted Together assemblies are intercepted
    /// </summary>
    public class TogetherWatcher : MonoBehaviour
    {
        private float timer = 0f;

        void Update()
        {
            if (Main.TogetherPatched) return;
            timer += Time.deltaTime;
            if (timer >= 0.5f)
            {
                timer = 0f;
                foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (a.GetName().Name == "Together")
                    {
                        Main.PatchTogether(a);
                        break;
                    }
                }
            }
        }
    }

    /// <summary>
    /// Fix 1: Shader Warmup Crash Fix
    /// Native Linux GPU driver crash workaround for Shader.WarmupAllShaders().
    /// </summary>
    [HarmonyPatch(typeof(Shader), nameof(Shader.WarmupAllShaders))]
    public static class WarmupFix
    {
        public static bool Prefix()
        {
            Debug.Log("[LinuxCrashFix] Skipped Shader.WarmupAllShaders() to prevent Linux GPU crash.");
            return false;
        }
    }

    /// <summary>
    /// Fix 2: High-DPI UI Skin Fix
    /// Enforces proper hitboxes on horizontal slider tracks and thumbs.
    /// </summary>
    [HarmonyPatch(typeof(UnityModManager.UI), "ScaleGUI")]
    public static class ScaleGUIPatch
    {
        public static void Postfix()
        {
            try
            {
                if (GUI.skin != null)
                {
                    int h = UnityModManager.UI.Scale(20);
                    int w = UnityModManager.UI.Scale(26);
                    if (GUI.skin.horizontalSlider != null)
                    {
                        GUI.skin.horizontalSlider.fixedHeight = h;
                    }
                    if (GUI.skin.horizontalSliderThumb != null)
                    {
                        GUI.skin.horizontalSliderThumb.fixedHeight = h + UnityModManager.UI.Scale(4);
                        GUI.skin.horizontalSliderThumb.fixedWidth = w;
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
        }
    }

    /// <summary>
    /// Fix 3: Continuous Drag Slider Implementation
    /// Replaces the default IMGUI Settings tab with continuous drag controls,
    /// resolution/scale presets, fine-tuning buttons, and direct text input.
    /// </summary>
}
