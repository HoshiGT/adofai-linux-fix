// UMMInjector — UMM Assembly 注入器 (Linux, 仿官方 Console 安装器的 dnlib 手法)
//
// 用法: mono UMMInjector.exe <command> <gamePath>
//   status   输出单行 JSON: injected/backup/umm_files/umm_version/entry_assembly/entry_point
//   inject   备份入口程序集 → 嵌入 UnityModManagerStarter → 在入口方法前插入 call → 写回
//            (要求 Managed/UnityModManager/UnityModManager.dll 已存在, 幂等: 先移除旧补丁)
//   unpatch  移除补丁 (call 指令 + Starter 类型), 不动 UMM 文件
//   restore  用 <入口程序集>.original_ 覆盖回原文件
//
// 编译: scripts/build_injector.sh
using System;
using System.IO;
using System.Linq;
using System.Xml;
using dnlib.DotNet;
using dnlib.DotNet.Emit;

class UMMInjector
{
    const string StarterNs = "UnityModManagerNet.Injection";
    const string StarterName = "UnityModManagerStarter";
    // ADOFAI 官方安装器使用的入口点; Managed/UnityModManager/Config.xml 存在时以其为准
    const string DefaultEntryPoint = "[UnityEngine.CoreModule.dll]UnityEngine.MonoBehaviour.cctor:Before";

    static string gamePath, managedPath, managerPath, entryPoint;
    static string entryAsmName, entryAsmPath, originalAsmPath;

    static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.WriteLine("ERR: usage: mono UMMInjector.exe <status|inject|unpatch|restore> <gamePath>");
            return 2;
        }
        gamePath = Path.GetFullPath(args[1]);
        managedPath = FindManaged(gamePath);
        if (managedPath == null)
        {
            Console.WriteLine("ERR: Managed folder not found in " + gamePath);
            return 1;
        }
        managerPath = Path.Combine(managedPath, "UnityModManager");
        entryPoint = ReadEntryPoint();

        // 解析 "[Asm.dll]Namespace.Class.Method:Place"
        int rb = entryPoint.IndexOf(']');
        if (rb < 1 || entryPoint[0] != '[')
        {
            Console.WriteLine("ERR: bad entry point: " + entryPoint);
            return 1;
        }
        entryAsmName = entryPoint.Substring(1, rb - 1);
        entryAsmPath = Path.Combine(managedPath, entryAsmName);
        originalAsmPath = entryAsmPath + ".original_";

        try
        {
            switch (args[0])
            {
                case "status": return Status();
                case "inject": return Inject();
                case "unpatch": return Unpatch();
                case "restore": return Restore();
                default:
                    Console.WriteLine("ERR: unknown command " + args[0]);
                    return 2;
            }
        }
        catch (Exception e)
        {
            Console.WriteLine("ERR: " + e);
            return 1;
        }
    }

    static string FindManaged(string root)
    {
        // 优先 Linux 原生数据目录 (与 adofai_fix.get_managed_dir 一致),
        // 否则可能误中 Proton/Windows 版目录 (其注入走 doorstop, 不补 CoreModule)
        foreach (var name in new[] { "ADanceOfFireAndIce_Data", "A Dance of Fire and Ice_Data" })
        {
            var managed = Path.Combine(root, name, "Managed");
            if (Directory.Exists(managed))
                return managed;
        }
        foreach (var dir in Directory.GetDirectories(root))
        {
            var managed = Path.Combine(dir, "Managed");
            if (Directory.Exists(managed))
                return managed;
        }
        return null;
    }

    static string ReadEntryPoint()
    {
        var config = Path.Combine(managerPath, "Config.xml");
        if (File.Exists(config))
        {
            try
            {
                var doc = new XmlDocument();
                doc.Load(config);
                var node = doc.SelectSingleNode("/Config/EntryPoint");
                if (node != null && !string.IsNullOrEmpty(node.InnerText))
                    return node.InnerText;
            }
            catch { }
        }
        return DefaultEntryPoint;
    }

    // ---- 查询 ----

    static TypeDef FindStarter(ModuleDefMD module)
    {
        return module.Types.FirstOrDefault(t => t.FullName == StarterNs + "." + StarterName);
    }

    static TypeDef FindLegacy(ModuleDefMD module)
    {
        return module.Types.FirstOrDefault(t => t.Name == "UnityModManager" && t.Methods.Any(m => m.Name == "Start"));
    }

    static int Status()
    {
        bool injected = false, backup = File.Exists(originalAsmPath), ummFiles = File.Exists(Path.Combine(managerPath, "UnityModManager.dll"));
        string ummVersion = null;
        if (File.Exists(entryAsmPath))
        {
            var module = ModuleDefMD.Load(File.ReadAllBytes(entryAsmPath));
            injected = FindStarter(module) != null || FindLegacy(module) != null;
        }
        if (ummFiles)
        {
            try
            {
                var mm = ModuleDefMD.Load(File.ReadAllBytes(Path.Combine(managerPath, "UnityModManager.dll")));
                ummVersion = mm.Assembly.Version.ToString();
            }
            catch { }
        }
        Console.WriteLine("{\"injected\":" + (injected ? "true" : "false")
            + ",\"backup\":" + (backup ? "true" : "false")
            + ",\"umm_files\":" + (ummFiles ? "true" : "false")
            + ",\"umm_version\":" + JsonStr(ummVersion)
            + ",\"entry_assembly\":" + JsonStr(entryAsmName)
            + ",\"entry_point\":" + JsonStr(entryPoint) + "}");
        return 0;
    }

    static string JsonStr(string s)
    {
        if (s == null) return "null";
        return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }

    // ---- 注入 / 移除 ----

    // 定位入口方法并移除已有补丁(内存中); 返回是否找到入口方法
    static bool StripPatch(ModuleDefMD module)
    {
        var starter = FindStarter(module);
        var legacy = starter == null ? FindLegacy(module) : null;
        var patchedType = starter ?? legacy;
        if (patchedType != null)
        {
            var start = patchedType.Methods.FirstOrDefault(m => m.Name == "Start");
            var cls = module.Find(EntryClass(), false);
            if (cls != null && start != null)
            {
                var methodDef = FindEntryMethod(cls);
                if (methodDef?.Body != null)
                {
                    foreach (var instr in methodDef.Body.Instructions.ToList())
                    {
                        if (instr.OpCode == OpCodes.Call && instr.Operand == start)
                        {
                            methodDef.Body.Instructions.Remove(instr);
                            break;
                        }
                    }
                }
            }
            module.Types.Remove(patchedType);
        }
        return true;
    }

    static string EntryClass()
    {
        // "[Asm.dll]Namespace.Class.Method:Place" → "Namespace.Class"
        var body = entryPoint.Substring(entryPoint.IndexOf(']') + 1);
        var dot = body.Substring(0, body.LastIndexOf('.'));
        return dot;
    }

    static MethodDef FindEntryMethod(TypeDef cls)
    {
        var body = entryPoint.Substring(entryPoint.IndexOf(']') + 1);
        var method = body.Substring(body.LastIndexOf('.') + 1);
        var colon = method.IndexOf(':');
        if (colon >= 0) method = method.Substring(0, colon);
        if (method == "cctor") method = ".cctor";
        else if (method == "ctor") method = ".ctor";
        return cls.Methods.FirstOrDefault(m => m.Name == method);
    }

    static bool EntryPlaceIsBefore()
    {
        var p = entryPoint;
        var colon = p.LastIndexOf(':');
        return colon < 0 || !p.Substring(colon + 1).Equals("After", StringComparison.OrdinalIgnoreCase);
    }

    static int Inject()
    {
        if (!File.Exists(Path.Combine(managerPath, "UnityModManager.dll")))
        {
            Console.WriteLine("ERR: UnityModManager.dll not found in " + managerPath);
            return 1;
        }
        if (!File.Exists(entryAsmPath))
        {
            Console.WriteLine("ERR: entry assembly not found: " + entryAsmPath);
            return 1;
        }
        if (!File.Exists(originalAsmPath))
            File.Copy(entryAsmPath, originalAsmPath, false);

        var module = ModuleDefMD.Load(File.ReadAllBytes(entryAsmPath));
        StripPatch(module); // 幂等: 先清掉旧补丁

        var cls = module.Find(EntryClass(), false);
        if (cls == null)
        {
            Console.WriteLine("ERR: entry class not found: " + EntryClass());
            return 1;
        }
        var methodDef = FindEntryMethod(cls);
        if (methodDef?.Body == null)
        {
            Console.WriteLine("ERR: entry method not found in " + EntryClass());
            return 1;
        }

        // 把本 exe 中的 Starter 类型移植进目标程序集 (与官方安装器相同)
        var self = ModuleDefMD.Load(typeof(UMMInjector).Assembly.Location);
        var starter = self.Types.First(t => t.FullName == StarterNs + "." + StarterName);
        self.Types.Remove(starter);
        module.Types.Add(starter);

        var startMethod = starter.Methods.First(m => m.Name == "Start");
        var instr = OpCodes.Call.ToInstruction(startMethod);
        if (EntryPlaceIsBefore())
            methodDef.Body.Instructions.Insert(0, instr);
        else
            methodDef.Body.Instructions.Insert(methodDef.Body.Instructions.Count - 1, instr);

        module.Write(entryAsmPath);
        Console.WriteLine("OK: injected into " + entryAsmName);
        return 0;
    }

    static int Unpatch()
    {
        if (!File.Exists(entryAsmPath))
        {
            Console.WriteLine("ERR: entry assembly not found: " + entryAsmPath);
            return 1;
        }
        var module = ModuleDefMD.Load(File.ReadAllBytes(entryAsmPath));
        var had = FindStarter(module) != null || FindLegacy(module) != null;
        if (!had)
        {
            Console.WriteLine("OK: no patch present");
            return 0;
        }
        StripPatch(module);
        module.Write(entryAsmPath);
        Console.WriteLine("OK: patch removed from " + entryAsmName);
        return 0;
    }

    static int Restore()
    {
        if (!File.Exists(originalAsmPath))
        {
            Console.WriteLine("ERR: backup not found: " + originalAsmPath);
            return 1;
        }
        File.Copy(originalAsmPath, entryAsmPath, true);
        Console.WriteLine("OK: restored " + entryAsmName + " from backup");
        return 0;
    }
}

// 与官方安装器嵌入的 Starter 完全一致 — 运行时从自身位置反推 UMM dll 并启动
namespace UnityModManagerNet.Injection
{
    public class UnityModManagerStarter
    {
        public static void Start()
        {
            try
            {
                var file = Path.Combine(Path.Combine(Path.GetDirectoryName(new Uri(System.Reflection.Assembly.GetExecutingAssembly().CodeBase).LocalPath), "UnityModManager"), "UnityModManager.dll");
                Console.WriteLine("[Assembly] Loading UnityModManager by " + file);

                var assembly = System.Reflection.Assembly.LoadFrom(file);
                var injector = assembly.GetType("UnityModManagerNet.Injector");
                injector.GetMethod("Run", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public).Invoke(null, new object[] { false });
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
            }
        }
    }
}
