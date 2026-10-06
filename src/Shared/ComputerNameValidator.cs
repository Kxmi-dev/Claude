namespace Lkds.Shared;

public static class ComputerNameValidator
{
    public const int MaxLength = 15;

    /// <summary>Gibt eine verständliche Fehlermeldung zurück oder null, wenn der Name gültig ist.</summary>
    public static string? Validate(string? name)
    {
        if (string.IsNullOrWhiteSpace(name))
            return "Bitte einen Computernamen eingeben.";
        if (name.Length > MaxLength)
            return $"Der Computername darf höchstens {MaxLength} Zeichen lang sein.";
        if (name.StartsWith('-') || name.EndsWith('-'))
            return "Der Computername darf nicht mit einem Bindestrich beginnen oder enden.";
        if (!name.All(c => c is (>= 'a' and <= 'z') or (>= 'A' and <= 'Z') or (>= '0' and <= '9') or '-'))
            return "Erlaubt sind nur Buchstaben (ohne Umlaute), Ziffern und Bindestriche.";
        if (name.All(char.IsDigit))
            return "Der Computername darf nicht nur aus Ziffern bestehen.";
        return null;
    }
}
