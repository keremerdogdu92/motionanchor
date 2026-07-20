using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class MotionAnchorUnity6Acceptance
{
    private const string AssetRoot = "Assets/MotionAnchor/Unity6Acceptance";
    private const string ReportPath = "artifacts/acceptance/unity6/report.json";

    [InitializeOnLoadMethod]
    private static void RunWhenRequested()
    {
        var marker = Path.Combine(Directory.GetCurrentDirectory(), "motionanchor-unity6-acceptance.run");
        if (!File.Exists(marker)) return;
        File.Delete(marker);
        EditorApplication.delayCall += Run;
    }
    public static void Run()
    {
        try
        {
            MotionAnchorAnimationImporter.ImportAllPending();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            Validate();
            WriteReport(true, "Unity 6 import acceptance passed.");
            EditorApplication.Exit(0);
        }
        catch (Exception error)
        {
            WriteReport(false, error.ToString());
            Debug.LogException(error);
            EditorApplication.Exit(1);
        }
    }

    private static void Validate()
    {
        var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(AssetRoot + "/Unity6Acceptance.anim");
        if (clip == null) throw new InvalidOperationException("AnimationClip was not created.");
        if (Math.Abs(clip.frameRate - 12f) > 0.001f) throw new InvalidOperationException("Unexpected clip frame rate.");
        var settings = AnimationUtility.GetAnimationClipSettings(clip);
        if (!settings.loopTime) throw new InvalidOperationException("Loop flag was not preserved.");

        var sprites = Enumerable.Range(1, 3)
            .Select(index => AssetDatabase.LoadAssetAtPath<Sprite>($"{AssetRoot}/Frames/Unity6Acceptance_frame_{index:0000}.png"))
            .ToArray();
        if (sprites.Any(sprite => sprite == null)) throw new InvalidOperationException("One or more sprites failed to import.");
        if (sprites.Any(sprite => Math.Abs(sprite.pixelsPerUnit - 100f) > 0.001f))
            throw new InvalidOperationException("Sprite PPU does not match the importer contract.");
        if (sprites.Any(sprite => Vector2.Distance(sprite.pivot, new Vector2(8f, 0f)) > 0.01f))
            throw new InvalidOperationException("Sprite pivot does not match the canonical bottom-center pivot.");

        var binding = EditorCurveBinding.PPtrCurve(string.Empty, typeof(SpriteRenderer), "m_Sprite");
        var keys = AnimationUtility.GetObjectReferenceCurve(clip, binding);
        if (keys == null || keys.Length != 3) throw new InvalidOperationException("Clip frame count is not 3.");
        if (!keys.Select(key => key.value.name).SequenceEqual(new[] {
            "Unity6Acceptance_frame_0001", "Unity6Acceptance_frame_0002", "Unity6Acceptance_frame_0003" }))
            throw new InvalidOperationException("Clip frame order is incorrect.");
    }

    private static void WriteReport(bool passed, string message)
    {
        var report = new AcceptanceReport
        {
            passed = passed,
            unityVersion = Application.unityVersion,
            assetName = "Unity6Acceptance",
            frameCount = passed ? 3 : 0,
            frameRate = passed ? 12f : 0f,
            loop = passed,
            pixelsPerUnit = passed ? 100f : 0f,
            pivot = passed ? "bottom-center" : string.Empty,
            message = message
        };
        Directory.CreateDirectory(Path.GetDirectoryName(ReportPath));
        File.WriteAllText(ReportPath, JsonUtility.ToJson(report, true));
    }

    [Serializable]
    private sealed class AcceptanceReport
    {
        public bool passed;
        public string unityVersion;
        public string assetName;
        public int frameCount;
        public float frameRate;
        public bool loop;
        public float pixelsPerUnit;
        public string pivot;
        public string message;
    }
}

