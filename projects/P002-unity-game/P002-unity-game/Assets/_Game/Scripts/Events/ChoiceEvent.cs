using System;

namespace FortressCity
{
    public class ChoiceEvent
    {
        public string title;
        public string description;
        public bool   isPositive = true;
        public string choiceALabel;
        public string choiceBLabel;
        public Action onChoiceA;
        public Action onChoiceB;
    }
}
