import datetime


class FrontendManager:
    time_gap = 3

    def __init__(self, board) -> None:
        self.frontends = {}
        self.board = board
        self.validIds = []
        self.loadSecret()

    def loadSecret(self):
        '''TODO, load a document of valid id'''

    '''Check if secret is valid, and if the frontend update too frequently, if legal action, updateboard'''

    def updateChange(self, id, row, col, color):
        if id not in self.validIds:
            '''TODO: Check if netid is valid and check the timestamp for this netid'''

        if id not in self.frontends.keys():
            self.frontends[id] = datetime.datetime.now()
            self.board.update_current_board(
                row, col, int(color))
            return "Success", 200

        else:
            if self.frontends[id] + datetime.timedelta(0, FrontendManager.time_gap) < datetime.datetime.now():
                self.frontends[id] = datetime.datetime.now()
                self.board.update_current_board(
                    row, col, int(color))
                return "Success", 200
            else:
                return "Too freqeunt update", 400
