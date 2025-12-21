namespace Piwnica.Common;

public static class ExtString
{
    public static bool IsNullOrEmpty(this string str)
    {
        return str == null || str.Length == 0;
    }
}
