using System;
using System.Linq;

namespace Piwnica.Common;

public static class EnumTraits<TEnum>
    where TEnum : Enum
{
    public static readonly int UniqueNameCount;

    static EnumTraits()
    {
        UniqueNameCount = Enum.GetNames(typeof(TEnum)).Distinct().Count();
    }
}
