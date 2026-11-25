"""Review package dispatcher for Octopus and all earlier films."""
import package_review as package
import build_octopus as current
package.current = current
if __name__ == "__main__":
    package.main()
