using System.Collections.Generic;

namespace Piwnica.Common;

static class ExtDictionary
{
    public static TValue GetOrCreate<TKey, TValue>(
        this Dictionary<TKey, TValue> dictionary,
        TKey key
    )
        where TValue : new()
    {
        if (dictionary.TryGetValue(key, out TValue value))
        {
            return value;
        }
        value = new();
        dictionary.Add(key, value);
        return value;
    }
}
