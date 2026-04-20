using UnityEngine;
using System.IO;

namespace FortressCity
{
    public static class SaveManager
    {
        static string SavePath => Path.Combine(Application.persistentDataPath, "save.json");

        public static void Save(CityData city)
        {
            File.WriteAllText(SavePath, JsonUtility.ToJson(city, true));
        }

        public static CityData Load()
        {
            if (!File.Exists(SavePath)) return null;
            try   { return JsonUtility.FromJson<CityData>(File.ReadAllText(SavePath)); }
            catch { return null; }
        }

        public static void Delete()
        {
            if (File.Exists(SavePath)) File.Delete(SavePath);
        }
    }
}
