using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;

namespace FortressCity
{
    // Attach to a GameObject in the Boot scene.
    // Waits one frame for GameManager to initialize, then loads City.
    public class BootController : MonoBehaviour
    {
        [SerializeField] private float delay = 0.5f;

        IEnumerator Start()
        {
            yield return new WaitForSeconds(delay);
            SceneManager.LoadScene("City");
        }
    }
}
