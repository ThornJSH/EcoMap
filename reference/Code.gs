// Code.gs

const SHEET_NAME = 'ecomap'; // 사용하는 시트 이름

/**
 * [헬퍼 함수] 현재 스크립트가 포함된 스프레드시트의 'ecomap' 시트를 가져옵니다.
 * 시트가 없으면 새로 생성하고 헤더를 추가합니다.
 */
function getActiveEcomapSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(SHEET_NAME);
  
  if (!sheet) {
    sheet = spreadsheet.insertSheet(SHEET_NAME);
    sheet.appendRow(['UserID', 'EcomapName', 'Type', 'Name', 'Relationship', 'Direction', 'X', 'Y']);
  }
  return sheet;
}

// 웹앱의 메인 진입점
function doGet(e) {
  const html = HtmlService.createTemplateFromFile('index').evaluate();
  html.setTitle('생태도 그리기 웹앱');
  html.addMetaTag('viewport', 'width=device-width, initial-scale=1');
  return html;
}

// HTML 파일 내에서 다른 HTML 파일을 포함시키기 위한 헬퍼 함수
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

// 현재 로그인한 사용자 이메일 가져오기
function getUserEmail() {
  return Session.getActiveUser().getEmail();
}

/**
 * 생태도 데이터를 시트에 저장합니다.
 * @param {object} dataToSave - 클라이언트에서 전송된 생태도 전체 데이터.
 */
function saveEcomapData(dataToSave) {
  try {
    const sheet = getActiveEcomapSheet();
    const userEmail = getUserEmail();
    const ecomapName = dataToSave.ecomapName;

    // 기존 데이터 삭제
    const data = sheet.getDataRange().getValues();
    const rowsToDelete = [];
    for (let i = data.length - 1; i >= 1; i--) {
      if (data[i][0] === userEmail && data[i][1] === ecomapName) {
        rowsToDelete.push(i + 1);
      }
    }
    rowsToDelete.forEach(rowNum => sheet.deleteRow(rowNum));

    // 새 데이터 추가
    const newRows = [];
    if (dataToSave.client) {
      const client = dataToSave.client;
      newRows.push([userEmail, ecomapName, 'Client', client.name, '', '', client.x, client.y]);
    }
    dataToSave.people.forEach(p => {
      newRows.push([userEmail, ecomapName, 'Person', p.name, p.relationship, p.direction, p.x, p.y]);
    });

    if (newRows.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, newRows.length, newRows[0].length).setValues(newRows);
    }

    return { status: 'success', message: '저장되었습니다.' };
  } catch (error) {
    return { status: 'error', message: error.toString() };
  }
}

/**
 * 현재 사용자의 저장된 생태도 목록을 가져옵니다.
 */
function getEcomapList() {
  const sheet = getActiveEcomapSheet();
  const data = sheet.getDataRange().getValues();
  const userEmail = getUserEmail();
  const ecomapNames = new Set();
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === userEmail) {
      ecomapNames.add(data[i][1]);
    }
  }
  return Array.from(ecomapNames);
}

/**
 * 특정 생태도의 데이터를 불러옵니다.
 * @param {string} ecomapName - 불러올 생태도의 이름.
 */
function loadEcomapData(ecomapName) {
  const sheet = getActiveEcomapSheet();
  const data = sheet.getDataRange().getValues();
  const userEmail = getUserEmail();
  const result = { client: null, people: [] };

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (row[0] === userEmail && row[1] === ecomapName) {
      const node = { name: row[3], x: parseFloat(row[6]), y: parseFloat(row[7]) };
      if (row[2] === 'Client') {
        result.client = node;
      } else if (row[2] === 'Person') {
        node.relationship = row[4];
        node.direction = row[5];
        result.people.push(node);
      }
    }
  }
  return result;
}

/**
 * 선택된 생태도를 삭제합니다.
 * @param {string[]} ecomapNames - 삭제할 생태도 이름 배열.
 */
function deleteEcomaps(ecomapNames) {
  try {
    const sheet = getActiveEcomapSheet();
    const data = sheet.getDataRange().getValues();
    const userEmail = getUserEmail();
    const rowsToDelete = [];
    
    for (let i = data.length - 1; i >= 1; i--) {
      if (data[i][0] === userEmail && ecomapNames.includes(data[i][1])) {
        rowsToDelete.push(i + 1);
      }
    }

    rowsToDelete.sort((a, b) => b - a).forEach(rowNum => {
      sheet.deleteRow(rowNum);
    });

    return { status: 'success', message: '삭제되었습니다.' };
  } catch(error) {
    return { status: 'error', message: error.toString() };
  }
}