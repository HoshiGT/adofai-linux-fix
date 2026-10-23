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
    [HarmonyPatch(typeof(UnityModManager.UI), "DrawTab")]
    public static class DrawTabPatch
    {
        private static int activeSliderId = -1;
        private static readonly Dictionary<int, string> textBuffers = new Dictionary<int, string>();

        public static bool Prefix(UnityModManager.UI __instance, int tabId, ref UnityAction buttons)
        {
            if (tabId == 2) // Settings Tab
            {
                try
                {
                    DrawSettingsTab(__instance, ref buttons);
                    return false;
                }
                catch (Exception ex)
                {
                    Debug.LogException(ex);
                    return true;
                }
            }
            return true;
        }

        public static Exception Finalizer(Exception __exception)
        {
            if (__exception is ArgumentException && __exception.Message.Contains("Getting control"))
            {
                return null;
            }
            return __exception;
        }

        private static void DrawSettingsTab(UnityModManager.UI ui, ref UnityAction buttons)
        {
            var traverse = Traverse.Create(ui);
            var paramsObj = Traverse.Create(typeof(UnityModManager)).Property("Params").GetValue();
            var paramsTrav = Traverse.Create(paramsObj);

            var mWindowSizeTrav = traverse.Field("mWindowSize");
            var mExpectedWindowSizeTrav = traverse.Field("mExpectedWindowSize");
            var mUIScaleTrav = traverse.Field("mUIScale");
            var mExpectedUIScaleTrav = traverse.Field("mExpectedUIScale");
            var mUIScaleChangedTrav = traverse.Field("mUIScaleChanged");
            var mSelectedFontTrav = traverse.Field("mSelectedFont");

            Vector2 windowSize = mWindowSizeTrav.GetValue<Vector2>();
            Vector2 expectedWindowSize = mExpectedWindowSizeTrav.GetValue<Vector2>();
            float uiScale = mUIScaleTrav.GetValue<float>();
            float expectedUIScale = mExpectedUIScaleTrav.GetValue<float>();
            int selectedFont = mSelectedFontTrav.GetValue<int>();
            string[] mOSfonts = traverse.Field("mOSfonts").GetValue<string[]>();
            Vector2[] mScrollPosition = traverse.Field("mScrollPosition").GetValue<Vector2[]>();

            var minWidth = GUILayout.MinWidth(windowSize.x);
            if (mScrollPosition != null && mScrollPosition.Length > 2)
            {
                mScrollPosition[2] = GUILayout.BeginScrollView(mScrollPosition[2], minWidth);
            }
            else
            {
                GUILayout.BeginScrollView(Vector2.zero, minWidth);
            }

            GUILayout.BeginVertical("box");

            // Hotkey section
            GUILayout.BeginHorizontal();
            GUILayout.Label("Hotkey (default Ctrl+F10)", GUILayout.ExpandWidth(false));
            var hotkey = paramsTrav.Field("Hotkey").GetValue<KeyBinding>();
            if (hotkey != null)
            {
                UnityModManager.UI.DrawKeybindingSmart(hotkey, "UMM Hotkey", null, GUILayout.ExpandWidth(false));
            }
            GUILayout.EndHorizontal();

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Check updates section
            var mCheckUpdateStrings = Traverse.Create(typeof(UnityModManager.UI)).Field("mCheckUpdateStrings").GetValue<string[]>();
            if (mCheckUpdateStrings != null)
            {
                GUILayout.BeginHorizontal();
                GUILayout.Label("Check updates", GUILayout.ExpandWidth(false));
                int checkUpdates = paramsTrav.Field("CheckUpdates").GetValue<int>();
                if (UnityModManager.UI.ToggleGroup(ref checkUpdates, mCheckUpdateStrings, null, GUILayout.ExpandWidth(false)))
                {
                    paramsTrav.Field("CheckUpdates").SetValue(checkUpdates);
                }
                GUILayout.EndHorizontal();
            }

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Show on start section
            var mShowOnStartStrings = Traverse.Create(typeof(UnityModManager.UI)).Field("mShowOnStartStrings").GetValue<string[]>();
            if (mShowOnStartStrings != null)
            {
                GUILayout.BeginHorizontal();
                GUILayout.Label("Show this window on startup", GUILayout.ExpandWidth(false));
                int showOnStart = paramsTrav.Field("ShowOnStart").GetValue<int>();
                if (UnityModManager.UI.ToggleGroup(ref showOnStart, mShowOnStartStrings, null, GUILayout.ExpandWidth(false)))
                {
                    paramsTrav.Field("ShowOnStart").SetValue(showOnStart);
                }
                GUILayout.EndHorizontal();
            }

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Window size box
            GUILayout.BeginVertical("box");
            GUILayout.Label("Window size", UnityModManager.UI.bold, GUILayout.ExpandWidth(false));

            // Resolution Presets
            GUILayout.BeginHorizontal();
            GUILayout.Label("Presets: ", GUILayout.ExpandWidth(false));
            if (GUILayout.Button("Default (1708x1122)", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
            {
                expectedWindowSize.x = 1708;
                expectedWindowSize.y = 1122;
                textBuffers[1] = "1708";
                textBuffers[2] = "1122";
            }
            if (GUILayout.Button("1080p (1920x1080)", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
            {
                expectedWindowSize.x = Mathf.Min(Screen.width, 1920);
                expectedWindowSize.y = Mathf.Min(Screen.height, 1080);
                textBuffers[1] = ((int)expectedWindowSize.x).ToString();
                textBuffers[2] = ((int)expectedWindowSize.y).ToString();
            }
            if (GUILayout.Button("2K (2560x1440)", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
            {
                expectedWindowSize.x = Mathf.Min(Screen.width, 2560);
                expectedWindowSize.y = Mathf.Min(Screen.height, 1440);
                textBuffers[1] = ((int)expectedWindowSize.x).ToString();
                textBuffers[2] = ((int)expectedWindowSize.y).ToString();
            }
            if (GUILayout.Button("Full Display", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
            {
                expectedWindowSize.x = Screen.width;
                expectedWindowSize.y = Screen.height;
                textBuffers[1] = Screen.width.ToString();
                textBuffers[2] = Screen.height.ToString();
            }
            GUILayout.EndHorizontal();

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Width slider
            expectedWindowSize.x = RenderSmoothSlider(
                1,
                "Width ",
                expectedWindowSize.x,
                Mathf.Min(Screen.width, 960),
                Screen.width,
                20f,
                "{0:0}",
                "px",
                300
            );

            // Height slider
            expectedWindowSize.y = RenderSmoothSlider(
                2,
                "Height",
                expectedWindowSize.y,
                Mathf.Min(Screen.height, 720),
                Screen.height,
                20f,
                "{0:0}",
                "px",
                300
            );

            mExpectedWindowSizeTrav.SetValue(expectedWindowSize);

            if (GUILayout.Button("Apply Window Size", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
            {
                windowSize.x = (int)expectedWindowSize.x;
                windowSize.y = (int)expectedWindowSize.y;
                mWindowSizeTrav.SetValue(windowSize);
                traverse.Method("CalculateWindowPos").GetValue();
                paramsTrav.Field("WindowWidth").SetValue((float)windowSize.x);
                paramsTrav.Field("WindowHeight").SetValue((float)windowSize.y);
            }
            GUILayout.EndVertical();

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // UI Scale and Font box
            GUILayout.BeginVertical("box");
            GUILayout.Label("UI", UnityModManager.UI.bold, GUILayout.ExpandWidth(false));

            if (mOSfonts != null && mOSfonts.Length > 0)
            {
                GUILayout.Label("Font", GUILayout.ExpandWidth(false));
                UnityModManager.UI.PopupToggleGroup(ref selectedFont, mOSfonts, null, GUI.skin.button, GUILayout.Width(UnityModManager.UI.Scale(250)));
                mSelectedFontTrav.SetValue(selectedFont);
            }

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Scale Presets
            GUILayout.BeginHorizontal();
            GUILayout.Label("Scale Presets: ", GUILayout.ExpandWidth(false));
            float[] presets = new float[] { 1.0f, 1.25f, 1.42f, 1.50f, 1.75f, 2.0f };
            foreach (var p in presets)
            {
                if (GUILayout.Button($"{p * 100:0}%", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
                {
                    expectedUIScale = p;
                    textBuffers[3] = p.ToString("0.00");
                }
            }
            GUILayout.EndHorizontal();

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Scale slider
            expectedUIScale = RenderSmoothSlider(
                3,
                "Scale ",
                expectedUIScale,
                0.5f,
                5.0f,
                0.05f,
                "{0:0.00}",
                "",
                300
            );

            mExpectedUIScaleTrav.SetValue(expectedUIScale);

            if (GUILayout.Button("Apply UI Scale & Font", UnityModManager.UI.button, GUILayout.ExpandWidth(false)))
            {
                string chosenFont = (mOSfonts != null && selectedFont >= 0 && selectedFont < mOSfonts.Length) ? mOSfonts[selectedFont] : paramsTrav.Field("UIFont").GetValue<string>();
                if (uiScale != expectedUIScale || chosenFont != paramsTrav.Field("UIFont").GetValue<string>())
                {
                    mUIScaleChangedTrav.SetValue(true);
                    mUIScaleTrav.SetValue(expectedUIScale);
                    paramsTrav.Field("UIScale").SetValue(expectedUIScale);
                    paramsTrav.Field("UIFont").SetValue(chosenFont);
                }
            }
            GUILayout.EndVertical();

            GUILayout.Space(UnityModManager.UI.Scale(5));

            // Mod Hotkeys box
            GUILayout.BeginVertical("box");
            GUILayout.Label("Mods Hotkeys", UnityModManager.UI.bold, GUILayout.ExpandWidth(false));
            var mods = UnityModManager.modEntries;
            if (mods != null)
            {
                for (int i = 0, c = mods.Count; i < c; i++)
                {
                    GUILayout.BeginHorizontal();
                    GUILayout.Label($"{mods[i].Info.DisplayName}", GUILayout.Width(UnityModManager.UI.Scale(250)));
                    UnityModManager.UI.DrawKeybindingSmart(mods[i].Hotkey, "Hotkey", null, GUILayout.ExpandWidth(false));
                    GUILayout.EndHorizontal();
                    GUILayout.Space(UnityModManager.UI.Scale(5));
                }
            }
            GUILayout.EndVertical();

            GUILayout.EndVertical(); // outer box
            GUILayout.EndScrollView();
        }

        private static float RenderSmoothSlider(
            int sliderId,
            string label,
            float value,
            float min,
            float max,
            float step,
            string format,
            string unit,
            int baseWidth)
        {
            int trackWidth = UnityModManager.UI.Scale(baseWidth);
            int trackHeight = UnityModManager.UI.Scale(22);
            int thumbWidth = UnityModManager.UI.Scale(28);
            int thumbHeight = UnityModManager.UI.Scale(24);
            int btnWidth = UnityModManager.UI.Scale(32);
            int labelWidth = UnityModManager.UI.Scale(60);
            int inputWidth = UnityModManager.UI.Scale(70);

            GUILayout.BeginHorizontal();

            // Label
            GUILayout.Label(label, GUILayout.Width(labelWidth));

            // [-] Step down button
            if (GUILayout.Button("-", UnityModManager.UI.button, GUILayout.Width(btnWidth), GUILayout.Height(trackHeight)))
            {
                value = Mathf.Max(min, value - step);
                textBuffers[sliderId] = string.Format(format, value);
            }

            // Slider Track Rect
            Rect trackRect = GUILayoutUtility.GetRect(trackWidth, trackHeight, GUILayout.Width(trackWidth), GUILayout.Height(trackHeight));

            int controlID = GUIUtility.GetControlID(sliderId * 1000 + 555, FocusType.Passive, trackRect);
            Event e = Event.current;

            if (e != null)
            {
                Rect hitRect = new Rect(trackRect.x, trackRect.y - UnityModManager.UI.Scale(8), trackRect.width, trackRect.height + UnityModManager.UI.Scale(16));

                EventType evtType = e.GetTypeForControl(controlID);
                if (activeSliderId == sliderId)
                {
                    if (e.type == EventType.MouseDrag || e.rawType == EventType.MouseDrag)
                    {
                        evtType = EventType.MouseDrag;
                    }
                    else if (e.type == EventType.MouseUp || e.rawType == EventType.MouseUp)
                    {
                        evtType = EventType.MouseUp;
                    }
                }

                switch (evtType)
                {
                    case EventType.MouseDown:
                        if (e.button == 0 && hitRect.Contains(e.mousePosition))
                        {
                            GUIUtility.hotControl = controlID;
                            activeSliderId = sliderId;
                            float usableWidth = Mathf.Max(1f, trackRect.width);
                            float pct = Mathf.Clamp01((e.mousePosition.x - trackRect.x) / usableWidth);
                            value = min + pct * (max - min);
                            textBuffers[sliderId] = string.Format(format, value);
                            GUI.changed = true;
                            e.Use();
                        }
                        break;

                    case EventType.MouseDrag:
                        if (GUIUtility.hotControl == controlID || activeSliderId == sliderId)
                        {
                            float usableWidth = Mathf.Max(1f, trackRect.width);
                            float pct = Mathf.Clamp01((e.mousePosition.x - trackRect.x) / usableWidth);
                            value = min + pct * (max - min);
                            textBuffers[sliderId] = string.Format(format, value);
                            GUI.changed = true;
                            e.Use();
                        }
                        break;

                    case EventType.MouseUp:
                        if (GUIUtility.hotControl == controlID || activeSliderId == sliderId)
                        {
                            GUIUtility.hotControl = 0;
                            activeSliderId = -1;
                            e.Use();
                        }
                        break;

                    case EventType.Repaint:
                        try
                        {
                            if (activeSliderId == sliderId)
                            {
                                if (Input.GetMouseButton(0))
                                {
                                    float usableWidth = Mathf.Max(1f, trackRect.width);
                                    float pct = Mathf.Clamp01((e.mousePosition.x - trackRect.x) / usableWidth);
                                    value = min + pct * (max - min);
                                    textBuffers[sliderId] = string.Format(format, value);
                                }
                                else
                                {
                                    activeSliderId = -1;
                                    if (GUIUtility.hotControl == controlID)
                                    {
                                        GUIUtility.hotControl = 0;
                                    }
                                }
                            }
                        }
                        catch {}
                        break;
                }
            }

            // Render Slider Track
            GUI.Box(trackRect, GUIContent.none, GUI.skin.horizontalSlider);

            // Render Thumb
            float norm = Mathf.Clamp01((value - min) / (max - min));
            float thumbX = trackRect.x + norm * (trackRect.width - thumbWidth);
            float thumbY = trackRect.y + (trackRect.height - thumbHeight) / 2f;
            Rect thumbRect = new Rect(thumbX, thumbY, thumbWidth, thumbHeight);
            GUI.Box(thumbRect, GUIContent.none, GUI.skin.horizontalSliderThumb);

            // [+] Step up button
            if (GUILayout.Button("+", UnityModManager.UI.button, GUILayout.Width(btnWidth), GUILayout.Height(trackHeight)))
            {
                value = Mathf.Min(max, value + step);
                textBuffers[sliderId] = string.Format(format, value);
            }

            GUILayout.Space(UnityModManager.UI.Scale(6));

            // Direct text input
            if (!textBuffers.TryGetValue(sliderId, out var currentText))
            {
                currentText = string.Format(format, value);
                textBuffers[sliderId] = currentText;
            }

            string newText = GUILayout.TextField(currentText, GUILayout.Width(inputWidth), GUILayout.Height(trackHeight));
            if (newText != currentText)
            {
                textBuffers[sliderId] = newText;
                if (float.TryParse(newText, out float parsedVal))
                {
                    value = Mathf.Clamp(parsedVal, min, max);
                }
            }
            else if (activeSliderId == sliderId)
            {
                textBuffers[sliderId] = string.Format(format, value);
            }

            if (!string.IsNullOrEmpty(unit))
            {
                GUILayout.Label(unit, GUILayout.ExpandWidth(false));
            }

            GUILayout.EndHorizontal();

            return value;
        }
    }
}
