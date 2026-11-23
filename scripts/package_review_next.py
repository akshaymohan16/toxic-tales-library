"""Use the frozen exact-export packager with the versioned scene selector."""
import package_review as package
import build_next as current

package.current = current

if __name__ == '__main__':
    package.main()
