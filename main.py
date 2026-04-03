import sys

from PyQt5.QtWidgets import QApplication

from mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Annotation Tool")
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
